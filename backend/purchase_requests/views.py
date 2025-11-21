from rest_framework import status, generics, viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404
from .serializers import (
    RegisterSerializer, UserSerializer,
    PurchaseRequestListSerializer, PurchaseRequestDetailSerializer,
    PurchaseRequestCreateSerializer, PurchaseRequestUpdateSerializer,
    ReceiptSubmissionSerializer
)
from .models import PurchaseRequest, RequestStatus
from .permissions import IsStaff, IsAnyApprover, IsFinance, CanEditRequest
from .document_processing import process_proforma_upload, process_receipt_upload


class RegisterView(generics.CreateAPIView):
    """User registration endpoint"""
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            "user": UserSerializer(user).data,
            "tokens": {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    """User login endpoint"""
    username = request.data.get("username")
    password = request.data.get("password")
    
    if not username or not password:
        return Response(
            {"error": "Username and password are required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    user = authenticate(username=username, password=password)
    
    if user is None:
        return Response(
            {"error": "Invalid credentials"},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    # Generate tokens
    refresh = RefreshToken.for_user(user)
    
    return Response({
        "user": UserSerializer(user).data,
        "tokens": {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def profile_view(request):
    """Get current user profile"""
    return Response(UserSerializer(request.user).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """Logout user by blacklisting refresh token"""
    try:
        refresh_token = request.data.get("refresh")
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
        return Response({"message": "Logout successful"}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ==================== STAFF ENDPOINTS ====================

class StaffRequestViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Staff to manage their purchase requests.
    
    Staff can:
    - Create new requests
    - View their own requests
    - Update pending requests
    - Submit receipts
    """
    permission_classes = [IsAuthenticated, IsStaff]
    
    def get_queryset(self):
        """Staff can only see their own requests"""
        return PurchaseRequest.objects.filter(
            created_by=self.request.user
        ).prefetch_related('items', 'approvals', 'approvals__approver')
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return PurchaseRequestListSerializer
        elif self.action == 'create':
            return PurchaseRequestCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return PurchaseRequestUpdateSerializer
        return PurchaseRequestDetailSerializer
    
    def perform_create(self, serializer):
        """Set created_by to current user and process proforma if uploaded"""
        instance = serializer.save(created_by=self.request.user)
        
        # Process proforma if uploaded
        if instance.proforma:
            try:
                metadata = process_proforma_upload(instance.proforma)
                instance.proforma_metadata = metadata
                instance.save()
            except Exception as e:
                # Log error but don't fail the request creation
                print(f"Error processing proforma: {e}")
    
    def update(self, request, *args, **kwargs):
        """Only allow updating pending requests"""
        instance = self.get_object()
        if not instance.can_be_edited_by(request.user):
            return Response(
                {"error": "You can only edit your own pending requests"},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)
    
    def partial_update(self, request, *args, **kwargs):
        """Only allow partial updating pending requests"""
        instance = self.get_object()
        if not instance.can_be_edited_by(request.user):
            return Response(
                {"error": "You can only edit your own pending requests"},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().partial_update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        """Prevent deletion, return 405 Method Not Allowed"""
        return Response(
            {"error": "Deletion of requests is not allowed"},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    @action(detail=True, methods=['post'], url_path='submit-receipt')
    def submit_receipt(self, request, pk=None):
        """
        Submit receipt for an approved request
        POST /api/requests/{id}/submit-receipt/
        """
        purchase_request = self.get_object()
        
        # Validate status
        if purchase_request.status != RequestStatus.APPROVED:
            return Response(
                {"error": "Can only submit receipt for approved requests"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate and save receipt
        serializer = ReceiptSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        purchase_request.receipt = serializer.validated_data['receipt']
        
        # Process and validate receipt against PO
        try:
            po_metadata = purchase_request.purchase_order_metadata or {}
            if po_metadata:
                validation_results = process_receipt_upload(
                    purchase_request.receipt,
                    po_metadata
                )
                purchase_request.receipt_validation = validation_results
        except Exception as e:
            # Log error but don't fail receipt submission
            print(f"Error validating receipt: {e}")
            purchase_request.receipt_validation = {
                "error": str(e),
                "validated": False
            }
        
        purchase_request.save()
        
        return Response(
            PurchaseRequestDetailSerializer(purchase_request).data,
            status=status.HTTP_200_OK
        )


# ==================== APPROVER ENDPOINTS ====================

class ApproverRequestViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Approvers to view and act on purchase requests.
    
    Approvers can:
    - View pending requests that require their level of approval
    - View all requests (for context)
    - Approve or reject requests at their level
    """
    permission_classes = [IsAuthenticated, IsAnyApprover]
    
    def get_queryset(self):
        """
        Approvers can see all requests, but filtered by what needs their attention
        """
        user = self.request.user
        queryset = PurchaseRequest.objects.all().prefetch_related(
            'items', 'approvals', 'approvals__approver'
        )
        
        # Filter by status if requested
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by what requires attention (default for list view)
        if self.action == 'list':
            needs_attention = self.request.query_params.get('needs_attention', 'true')
            if needs_attention.lower() == 'true':
                if hasattr(user, 'profile'):
                    if user.profile.role == 'approver_level_1':
                        # Show pending requests without level 1 approval
                        queryset = queryset.filter(
                            status=RequestStatus.PENDING
                        ).exclude(
                            approvals__approver_level=1,
                            approvals__approved__isnull=False
                        )
                    elif user.profile.role == 'approver_level_2':
                        # Show pending requests with level 1 approval but without level 2
                        queryset = queryset.filter(
                            status=RequestStatus.PENDING,
                            approvals__approver_level=1,
                            approvals__approved=True
                        ).exclude(
                            approvals__approver_level=2,
                            approvals__approved__isnull=False
                        )
        
        return queryset.distinct()
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return PurchaseRequestListSerializer
        return PurchaseRequestDetailSerializer
    
    @action(detail=True, methods=['post'], url_path='approve')
    def approve_request(self, request, pk=None):
        """
        Approve a purchase request at the approver's level
        POST /api/approvals/{id}/approve/
        """
        from .serializers import ApprovalActionSerializer
        from .models import Approval, UserRole
        from django.utils import timezone
        from django.db import transaction
        
        purchase_request = self.get_object()
        user = request.user
        
        # Validate request status
        if purchase_request.status != RequestStatus.PENDING:
            return Response(
                {"error": "Can only approve pending requests"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate serializer
        serializer = ApprovalActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        approved = serializer.validated_data['approved']
        comments = serializer.validated_data.get('comments', '')
        
        # Determine approver level
        if not hasattr(user, 'profile'):
            return Response(
                {"error": "User profile not found"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if user.profile.role == UserRole.APPROVER_L1:
            approver_level = 1
        elif user.profile.role == UserRole.APPROVER_L2:
            approver_level = 2
        else:
            return Response(
                {"error": "User is not an approver"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if already approved/rejected at this level
        existing_approval = Approval.objects.filter(
            purchase_request=purchase_request,
            approver_level=approver_level
        ).first()
        
        if existing_approval and existing_approval.approved is not None:
            return Response(
                {"error": f"This request has already been {'approved' if existing_approval.approved else 'rejected'} at level {approver_level}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # For level 2, ensure level 1 is approved
        if approver_level == 2:
            level_1_approval = Approval.objects.filter(
                purchase_request=purchase_request,
                approver_level=1,
                approved=True
            ).first()
            
            if not level_1_approval:
                return Response(
                    {"error": "Level 1 approval is required before Level 2 can approve"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Create or update approval
        with transaction.atomic():
            if existing_approval:
                existing_approval.approved = approved
                existing_approval.comments = comments
                existing_approval.reviewed_at = timezone.now()
                existing_approval.save()
            else:
                Approval.objects.create(
                    purchase_request=purchase_request,
                    approver=user,
                    approver_level=approver_level,
                    approved=approved,
                    comments=comments,
                    reviewed_at=timezone.now()
                )
            
            # Update request status based on approval outcome
            if not approved:
                # Rejection at any level → request rejected
                purchase_request.status = RequestStatus.REJECTED
                purchase_request.rejected_at = timezone.now()
                purchase_request.save()
            else:
                # Check if fully approved (both levels approved)
                if approver_level == 2:
                    # Level 2 just approved, check if level 1 is also approved
                    level_1_approved = Approval.objects.filter(
                        purchase_request=purchase_request,
                        approver_level=1,
                        approved=True
                    ).exists()
                    
                    if level_1_approved:
                        purchase_request.status = RequestStatus.APPROVED
                        purchase_request.approved_at = timezone.now()
                        purchase_request.save()
                        
                        # Trigger automatic PO generation
                        try:
                            from .document_processing import generate_purchase_order
                            
                            # Prepare request data
                            request_data = {
                                'title': purchase_request.title,
                                'description': purchase_request.description,
                                'amount': str(purchase_request.amount),
                                'items': [
                                    {
                                        'name': item.item_name,
                                        'description': item.description,
                                        'quantity': item.quantity,
                                        'unit_price': str(item.unit_price),
                                        'total': str(item.total_price)
                                    }
                                    for item in purchase_request.items.all()
                                ]
                            }
                            
                            # Generate PO using proforma metadata
                            proforma_metadata = purchase_request.proforma_metadata or {}
                            po_data = generate_purchase_order(request_data, proforma_metadata)
                            
                            if po_data.get('generated'):
                                purchase_request.purchase_order_metadata = po_data
                                purchase_request.save()
                                
                        except Exception as e:
                            # Log error but don't fail the approval
                            print(f"Error generating PO: {e}")
        
        return Response(
            PurchaseRequestDetailSerializer(purchase_request).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'], url_path='reject')
    def reject_request(self, request, pk=None):
        """
        Reject a purchase request at the approver's level
        POST /api/approvals/{id}/reject/
        """
        # Reuse approve logic with approved=False
        request.data['approved'] = False
        return self.approve_request(request, pk)


# ==================== FINANCE ENDPOINTS ====================

class FinanceRequestViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Finance team to view approved purchase requests.
    
    Finance can:
    - View all approved requests
    - View all requests (for reporting)
    - Access request details including PO and receipts
    """
    permission_classes = [IsAuthenticated, IsFinance]
    
    def get_queryset(self):
        """
        Finance can see all requests, with filtering options
        """
        queryset = PurchaseRequest.objects.all().prefetch_related(
            'items', 'approvals', 'approvals__approver'
        )
        
        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        else:
            # By default, show only approved requests
            if self.action == 'list':
                queryset = queryset.filter(status=RequestStatus.APPROVED)
        
        # Filter by date range
        date_from = self.request.query_params.get('date_from', None)
        date_to = self.request.query_params.get('date_to', None)
        
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        # Filter by amount range
        amount_min = self.request.query_params.get('amount_min', None)
        amount_max = self.request.query_params.get('amount_max', None)
        
        if amount_min:
            queryset = queryset.filter(amount__gte=amount_min)
        if amount_max:
            queryset = queryset.filter(amount__lte=amount_max)
        
        return queryset.order_by('-approved_at', '-created_at')
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return PurchaseRequestListSerializer
        return PurchaseRequestDetailSerializer
    
    @action(detail=False, methods=['get'], url_path='statistics')
    def statistics(self, request):
        """
        Get financial statistics for approved requests
        GET /api/finance/statistics/
        """
        from django.db.models import Sum, Count, Avg
        from decimal import Decimal
        
        approved_requests = PurchaseRequest.objects.filter(status=RequestStatus.APPROVED)
        
        stats = {
            "total_requests": approved_requests.count(),
            "total_amount": approved_requests.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00'),
            "average_amount": approved_requests.aggregate(Avg('amount'))['amount__avg'] or Decimal('0.00'),
            "requests_with_receipt": approved_requests.filter(receipt__isnull=False).count(),
            "requests_without_receipt": approved_requests.filter(receipt__isnull=True).count(),
        }
        
        return Response(stats, status=status.HTTP_200_OK)


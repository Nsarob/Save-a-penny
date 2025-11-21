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
        """Set created_by to current user"""
        serializer.save(created_by=self.request.user)
    
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
        purchase_request.save()
        
        return Response(
            PurchaseRequestDetailSerializer(purchase_request).data,
            status=status.HTTP_200_OK
        )


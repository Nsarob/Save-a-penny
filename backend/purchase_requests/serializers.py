from rest_framework import serializers
from django.contrib.auth.models import User
from .models import UserProfile, UserRole, PurchaseRequest, Approval, RequestItem, RequestStatus


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile"""
    class Meta:
        model = UserProfile
        fields = ["role", "department", "phone_number"]


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user with profile"""
    profile = UserProfileSerializer(read_only=True)
    
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "profile"]
        read_only_fields = ["id"]


class UserMinimalSerializer(serializers.ModelSerializer):
    """Minimal user serializer for nested representations"""
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name"]
        read_only_fields = ["id"]


class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(choices=UserRole.choices, write_only=True)
    department = serializers.CharField(required=False, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = User
        fields = ["username", "email", "password", "password_confirm", 
                 "first_name", "last_name", "role", "department", "phone_number"]

    def validate(self, data):
        """Validate passwords match"""
        if data["password"] != data["password_confirm"]:
            raise serializers.ValidationError({"password": "Passwords do not match"})
        return data

    def create(self, validated_data):
        """Create user and profile"""
        # Remove extra fields
        validated_data.pop("password_confirm")
        role = validated_data.pop("role")
        department = validated_data.pop("department", "")
        phone_number = validated_data.pop("phone_number", "")
        
        # Create user
        user = User.objects.create_user(**validated_data)
        
        # Create profile
        UserProfile.objects.create(
            user=user,
            role=role,
            department=department,
            phone_number=phone_number
        )
        
        return user


class RequestItemSerializer(serializers.ModelSerializer):
    """Serializer for request items"""
    total_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    class Meta:
        model = RequestItem
        fields = ["id", "item_name", "description", "quantity", "unit_price", "total_price"]
        read_only_fields = ["id", "total_price"]


class ApprovalSerializer(serializers.ModelSerializer):
    """Serializer for approval records"""
    approver = UserMinimalSerializer(read_only=True)
    approver_level_display = serializers.CharField(source="get_approver_level_display", read_only=True)
    
    class Meta:
        model = Approval
        fields = ["id", "approver", "approver_level", "approver_level_display", 
                 "approved", "comments", "reviewed_at", "created_at"]
        read_only_fields = ["id", "approver", "reviewed_at", "created_at"]


class PurchaseRequestListSerializer(serializers.ModelSerializer):
    """Simplified serializer for list views"""
    created_by = UserMinimalSerializer(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    
    class Meta:
        model = PurchaseRequest
        fields = ["id", "title", "amount", "status", "status_display", 
                 "created_by", "created_at", "updated_at"]
        read_only_fields = ["id", "status", "created_by", "created_at", "updated_at"]


class PurchaseRequestDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single request view"""
    created_by = UserMinimalSerializer(read_only=True)
    items = RequestItemSerializer(many=True, read_only=True)
    approvals = ApprovalSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    
    # Computed properties
    requires_level_1_approval = serializers.BooleanField(read_only=True)
    requires_level_2_approval = serializers.BooleanField(read_only=True)
    is_fully_approved = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = PurchaseRequest
        fields = [
            "id", "title", "description", "amount", "status", "status_display",
            "created_by", "items", "approvals",
            "proforma", "proforma_metadata",
            "purchase_order", "purchase_order_metadata",
            "receipt", "receipt_metadata", "receipt_validation",
            "requires_level_1_approval", "requires_level_2_approval", "is_fully_approved",
            "created_at", "updated_at", "approved_at", "rejected_at"
        ]
        read_only_fields = [
            "id", "status", "created_by", "approvals", 
            "purchase_order", "purchase_order_metadata",
            "receipt_validation", "created_at", "updated_at", 
            "approved_at", "rejected_at"
        ]


class PurchaseRequestCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating purchase requests"""
    items = RequestItemSerializer(many=True, required=False)
    
    class Meta:
        model = PurchaseRequest
        fields = ["title", "description", "amount", "proforma", "items"]
    
    def validate_amount(self, value):
        """Validate amount is positive"""
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero")
        return value
    
    def create(self, validated_data):
        """Create request with items"""
        items_data = validated_data.pop("items", [])
        request = PurchaseRequest.objects.create(**validated_data)
        
        # Create items
        for item_data in items_data:
            RequestItem.objects.create(purchase_request=request, **item_data)
        
        return request


class PurchaseRequestUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating purchase requests (staff only, pending status)"""
    items = RequestItemSerializer(many=True, required=False)
    
    class Meta:
        model = PurchaseRequest
        fields = ["title", "description", "amount", "proforma", "items"]
    
    def validate(self, data):
        """Ensure request can be edited"""
        request = self.instance
        if request.status != RequestStatus.PENDING:
            raise serializers.ValidationError("Only pending requests can be edited")
        return data
    
    def update(self, instance, validated_data):
        """Update request and replace items"""
        items_data = validated_data.pop("items", None)
        
        # Update request fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Replace items if provided
        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                RequestItem.objects.create(purchase_request=instance, **item_data)
        
        return instance


class ReceiptSubmissionSerializer(serializers.Serializer):
    """Serializer for receipt submission"""
    receipt = serializers.FileField(required=True)
    
    def validate_receipt(self, value):
        """Validate receipt file"""
        # Check file size (10MB max)
        if value.size > 10485760:
            raise serializers.ValidationError("Receipt file size must be less than 10MB")
        
        # Check file type
        allowed_types = ['application/pdf', 'image/jpeg', 'image/png', 'image/jpg']
        if value.content_type not in allowed_types:
            raise serializers.ValidationError("Receipt must be PDF, JPEG, or PNG")
        
        return value

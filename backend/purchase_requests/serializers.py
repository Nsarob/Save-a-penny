from rest_framework import serializers
from django.contrib.auth.models import User
from .models import UserProfile, UserRole, PurchaseRequest, Approval, RequestItem


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

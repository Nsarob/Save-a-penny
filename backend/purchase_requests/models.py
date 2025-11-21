from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db.models import Q
import uuid


class UserRole(models.TextChoices):
    """User role choices for the procurement system"""
    STAFF = "staff", "Staff"
    APPROVER_L1 = "approver_level_1", "Approver Level 1"
    APPROVER_L2 = "approver_level_2", "Approver Level 2"
    FINANCE = "finance", "Finance"


class UserProfile(models.Model):
    """Extended user profile with role information"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.STAFF)
    department = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_profiles"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"


class RequestStatus(models.TextChoices):
    """Purchase request status choices"""
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class PurchaseRequest(models.Model):
    """Main purchase request model"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField()
    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    status = models.CharField(
        max_length=20, 
        choices=RequestStatus.choices, 
        default=RequestStatus.PENDING
    )
    
    # User relationships
    created_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name="created_requests"
    )
    
    # Document uploads
    proforma = models.FileField(upload_to="proformas/", null=True, blank=True)
    proforma_metadata = models.JSONField(null=True, blank=True, help_text="Extracted proforma data")
    
    purchase_order = models.FileField(upload_to="purchase_orders/", null=True, blank=True)
    purchase_order_metadata = models.JSONField(null=True, blank=True, help_text="Generated PO data")
    
    receipt = models.FileField(upload_to="receipts/", null=True, blank=True)
    receipt_metadata = models.JSONField(null=True, blank=True, help_text="Extracted receipt data")
    receipt_validation = models.JSONField(null=True, blank=True, help_text="Receipt validation results")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = "purchase_requests"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["created_by", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"

    @property
    def requires_level_1_approval(self):
        """Check if Level 1 approval is required"""
        return not self.approvals.filter(approver_level=1, approved=True).exists()

    @property
    def requires_level_2_approval(self):
        """Check if Level 2 approval is required"""
        return not self.approvals.filter(approver_level=2, approved=True).exists()

    @property
    def is_fully_approved(self):
        """Check if all required approvals are completed"""
        level_1_approved = self.approvals.filter(approver_level=1, approved=True).exists()
        level_2_approved = self.approvals.filter(approver_level=2, approved=True).exists()
        return level_1_approved and level_2_approved

    @property
    def is_rejected(self):
        """Check if request has been rejected"""
        return self.approvals.filter(approved=False).exists()

    def can_be_edited_by(self, user):
        """Check if user can edit this request"""
        return (
            self.created_by == user and 
            self.status == RequestStatus.PENDING and
            hasattr(user, 'profile') and
            user.profile.role == UserRole.STAFF
        )


class Approval(models.Model):
    """Approval tracking model for multi-level approvals"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase_request = models.ForeignKey(
        PurchaseRequest, 
        on_delete=models.CASCADE, 
        related_name="approvals"
    )
    approver = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name="approvals_made"
    )
    approver_level = models.IntegerField(
        choices=[(1, "Level 1"), (2, "Level 2")],
        help_text="1 for Level 1 approver, 2 for Level 2 approver"
    )
    approved = models.BooleanField(null=True, blank=True, help_text="True=Approved, False=Rejected, None=Pending")
    comments = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "approvals"
        ordering = ["approver_level", "-created_at"]
        unique_together = [["purchase_request", "approver_level"]]
        indexes = [
            models.Index(fields=["purchase_request", "approver_level"]),
            models.Index(fields=["approver", "-created_at"]),
        ]

    def __str__(self):
        status = "Pending"
        if self.approved is True:
            status = "Approved"
        elif self.approved is False:
            status = "Rejected"
        return f"Level {self.approver_level} - {status} by {self.approver.username}"


class RequestItem(models.Model):
    """Individual items in a purchase request"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase_request = models.ForeignKey(
        PurchaseRequest, 
        on_delete=models.CASCADE, 
        related_name="items"
    )
    item_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    total_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        editable=False
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "request_items"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.item_name} x {self.quantity}"

    def save(self, *args, **kwargs):
        """Calculate total price before saving"""
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)


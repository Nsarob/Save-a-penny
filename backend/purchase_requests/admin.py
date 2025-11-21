from django.contrib import admin
from .models import UserProfile, PurchaseRequest, Approval, RequestItem


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "role", "department", "created_at"]
    list_filter = ["role", "created_at"]
    search_fields = ["user__username", "user__email", "department"]
    readonly_fields = ["created_at", "updated_at"]


class ApprovalInline(admin.TabularInline):
    model = Approval
    extra = 0
    readonly_fields = ["created_at", "updated_at", "reviewed_at"]


class RequestItemInline(admin.TabularInline):
    model = RequestItem
    extra = 1
    readonly_fields = ["total_price", "created_at", "updated_at"]


@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display = ["title", "created_by", "amount", "status", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["title", "description", "created_by__username"]
    readonly_fields = ["id", "created_at", "updated_at", "approved_at", "rejected_at"]
    inlines = [RequestItemInline, ApprovalInline]
    
    fieldsets = (
        ("Basic Information", {
            "fields": ("id", "title", "description", "amount", "status", "created_by")
        }),
        ("Documents", {
            "fields": ("proforma", "proforma_metadata", "purchase_order", 
                      "purchase_order_metadata", "receipt", "receipt_metadata", 
                      "receipt_validation")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at", "approved_at", "rejected_at")
        }),
    )


@admin.register(Approval)
class ApprovalAdmin(admin.ModelAdmin):
    list_display = ["purchase_request", "approver", "approver_level", "approved", "reviewed_at"]
    list_filter = ["approver_level", "approved", "created_at"]
    search_fields = ["purchase_request__title", "approver__username"]
    readonly_fields = ["id", "created_at", "updated_at", "reviewed_at"]


@admin.register(RequestItem)
class RequestItemAdmin(admin.ModelAdmin):
    list_display = ["item_name", "purchase_request", "quantity", "unit_price", "total_price"]
    search_fields = ["item_name", "purchase_request__title"]
    readonly_fields = ["id", "total_price", "created_at", "updated_at"]


"""
Document Processing Utilities for AI-based extraction and validation
Uses OpenAI API, pytesseract, and pdfplumber for document processing
"""
import os
import json
from decimal import Decimal
from typing import Dict, Any, Optional, List
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
import pdfplumber
from PIL import Image
import pytesseract
from openai import OpenAI


# Initialize OpenAI client
client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None


def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from PDF using pdfplumber"""
    try:
        with pdfplumber.open(file_path) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() or ""
        return text.strip()
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return ""


def extract_text_from_image(file_path: str) -> str:
    """Extract text from image using OCR (pytesseract)"""
    try:
        image = Image.open(file_path)
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception as e:
        print(f"Error extracting text from image: {e}")
        return ""


def extract_text_from_file(file_obj: UploadedFile) -> str:
    """
    Extract text from uploaded file (PDF or image)
    Saves file temporarily, extracts text, then cleans up
    """
    # Save file temporarily
    temp_path = f"/tmp/{file_obj.name}"
    with open(temp_path, 'wb+') as destination:
        for chunk in file_obj.chunks():
            destination.write(chunk)
    
    # Extract text based on file type
    content_type = file_obj.content_type
    if content_type == 'application/pdf':
        text = extract_text_from_pdf(temp_path)
    elif content_type in ['image/jpeg', 'image/png', 'image/jpg']:
        text = extract_text_from_image(temp_path)
    else:
        text = ""
    
    # Clean up
    try:
        os.remove(temp_path)
    except:
        pass
    
    return text


def extract_proforma_metadata_with_ai(text: str) -> Dict[str, Any]:
    """
    Extract proforma/quotation metadata using OpenAI API
    Returns structured data: vendor, items, prices, terms, etc.
    """
    if not client:
        return {
            "error": "OpenAI API key not configured",
            "extracted": False
        }
    
    try:
        prompt = f"""
        Extract the following information from this proforma invoice/quotation:
        
        1. Vendor name and contact details
        2. Invoice/Quote number
        3. Date
        4. List of items with descriptions, quantities, unit prices, and totals
        5. Subtotal, tax, and total amount
        6. Payment terms
        7. Delivery terms
        
        Proforma text:
        {text}
        
        Return the data as a JSON object with these keys:
        - vendor_name
        - vendor_contact (email, phone, address)
        - invoice_number
        - date
        - items (array of objects with: name, description, quantity, unit_price, total)
        - subtotal
        - tax_amount
        - total_amount
        - payment_terms
        - delivery_terms
        
        If any field is not found, use null.
        """
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a document processing assistant that extracts structured data from invoices and quotations. Always return valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        metadata = json.loads(response.choices[0].message.content)
        metadata["extracted"] = True
        metadata["raw_text"] = text[:500]  # Store first 500 chars for reference
        
        return metadata
        
    except Exception as e:
        return {
            "error": str(e),
            "extracted": False,
            "raw_text": text[:500]
        }


def generate_purchase_order(request_data: Dict[str, Any], proforma_metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate Purchase Order data from approved request and proforma
    Returns structured PO data
    """
    if not client:
        return {
            "error": "OpenAI API key not configured",
            "generated": False
        }
    
    try:
        prompt = f"""
        Generate a Purchase Order based on this approved purchase request and proforma:
        
        Request Details:
        - Title: {request_data.get('title')}
        - Description: {request_data.get('description')}
        - Amount: {request_data.get('amount')}
        - Items: {json.dumps(request_data.get('items', []))}
        
        Proforma Metadata:
        {json.dumps(proforma_metadata, indent=2)}
        
        Generate a Purchase Order with:
        1. PO Number (format: PO-YYYYMMDD-XXXX)
        2. Issue Date (today's date)
        3. Vendor details from proforma
        4. Buyer details (Company: Save-a-Penny Procurement)
        5. Items list with quantities and prices
        6. Payment terms
        7. Delivery terms and address
        8. Special instructions
        
        Return as JSON with these keys:
        - po_number
        - issue_date
        - vendor (name, contact)
        - buyer (name, contact, address)
        - items (array)
        - subtotal
        - tax_amount
        - total_amount
        - payment_terms
        - delivery_terms
        - delivery_address
        - special_instructions
        """
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a procurement assistant that generates formal purchase orders. Always return valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        po_data = json.loads(response.choices[0].message.content)
        po_data["generated"] = True
        
        return po_data
        
    except Exception as e:
        return {
            "error": str(e),
            "generated": False
        }


def validate_receipt_against_po(receipt_text: str, po_metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate receipt against Purchase Order
    Returns validation results with discrepancies flagged
    """
    if not client:
        return {
            "error": "OpenAI API key not configured",
            "validated": False
        }
    
    try:
        prompt = f"""
        Compare this receipt with the Purchase Order and identify any discrepancies:
        
        Receipt Text:
        {receipt_text}
        
        Purchase Order:
        {json.dumps(po_metadata, indent=2)}
        
        Check for:
        1. Vendor name matches
        2. Items match (names, quantities, prices)
        3. Total amount matches
        4. Any additional charges not in PO
        5. Any missing items from PO
        
        Return JSON with:
        - vendor_match (boolean)
        - vendor_issues (string or null)
        - items_match (boolean)
        - item_discrepancies (array of objects with: item, issue, po_price, receipt_price)
        - total_match (boolean)
        - total_discrepancy (object with: po_total, receipt_total, difference)
        - additional_charges (array of objects with: description, amount)
        - missing_items (array of item names)
        - overall_valid (boolean)
        - validation_summary (string)
        """
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a financial auditor that validates receipts against purchase orders. Always return valid JSON with detailed comparisons."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        validation = json.loads(response.choices[0].message.content)
        validation["validated"] = True
        validation["receipt_text"] = receipt_text[:500]  # Store first 500 chars
        
        return validation
        
    except Exception as e:
        return {
            "error": str(e),
            "validated": False,
            "receipt_text": receipt_text[:500]
        }


def process_proforma_upload(proforma_file: UploadedFile) -> Dict[str, Any]:
    """
    Main function to process proforma upload
    1. Extract text from file
    2. Use AI to extract metadata
    """
    # Extract text
    text = extract_text_from_file(proforma_file)
    
    if not text:
        return {
            "error": "Could not extract text from file",
            "extracted": False
        }
    
    # Extract metadata using AI
    metadata = extract_proforma_metadata_with_ai(text)
    
    return metadata


def process_receipt_upload(receipt_file: UploadedFile, po_metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main function to process receipt upload and validate against PO
    1. Extract text from receipt
    2. Validate against PO using AI
    """
    # Extract text
    text = extract_text_from_file(receipt_file)
    
    if not text:
        return {
            "error": "Could not extract text from receipt",
            "validated": False
        }
    
    # Validate against PO
    validation = validate_receipt_against_po(text, po_metadata)
    
    return validation

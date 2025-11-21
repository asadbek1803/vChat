# accounts/views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import render
from rest_framework_simplejwt.tokens import RefreshToken
from django.db.models import Q
import json
import logging
from .models import Account, Contact, Message
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

# ========================
# 🔑 TOKEN GENERATION
# ========================
def get_tokens_for_user(user):
    """Generate JWT tokens"""
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }

# ========================
# 📄 PAGES
# ========================
def index(request):
    """Login page"""
    logger.info(f"📄 Index page, path: {request.path}")
    return render(request, 'index.html')

def chat(request):
    """Chat page"""
    logger.info("💬 Chat page")
    return render(request, 'index.html')

# ========================
# 🔐 AUTHENTICATION
# ========================
@csrf_exempt
@require_http_methods(["POST"])
def telegram_auth_api(request):
    """Telegram authentication"""
    logger.info("📨 Telegram auth request")
    
    try:
        data = json.loads(request.body)
        telegram_id = data.get('id')
        first_name = data.get('first_name', 'Unknown')
        last_name = data.get('last_name', '')
        username = data.get('username', '') or f'user_{telegram_id}'
        
        if not telegram_id or not first_name:
            return JsonResponse({'success': False, 'error': 'Missing fields'}, status=400)
        
        # Create/Update user
        user, created = Account.objects.get_or_create(
            telegram_id=telegram_id,
            defaults={
                'first_name': first_name,
                'last_name': last_name,
                'username': username
            }
        )
        
        if not created:
            user.first_name = first_name
            user.last_name = last_name
            user.username = username
            user.is_online = True
            user.save()
        
        # Generate tokens
        tokens = get_tokens_for_user(user)
        
        # Get user's accepted contacts
        accepted_contacts = Contact.objects.filter(
            user=user, 
            is_accepted=True
        ).select_related('contact')
        
        # Get pending requests (where user is the receiver)
        pending_requests = Contact.objects.filter(
            contact=user,
            is_accepted=False
        ).select_related('user')
        
        # Combine all contacts
        contacts_data = []
        
        # Add accepted contacts
        for c in accepted_contacts:
            contacts_data.append({
                'id': c.contact.id,
                'user_id': c.user.id,
                'telegram_id': c.contact.telegram_id,
                'name': c.custom_name or c.contact.first_name,
                'username': c.contact.username,
                'is_online': c.contact.is_online,
                'is_accepted': True,
                'pending_from_them': False
            })
        
        # Add pending requests
        for c in pending_requests:
            contacts_data.append({
                'id': c.user.id,
                'user_id': c.user.id,
                'telegram_id': c.user.telegram_id,
                'name': c.custom_name or c.user.first_name,
                'username': c.user.username,
                'is_online': c.user.is_online,
                'is_accepted': False,
                'pending_from_them': True  # This is a request from them to us
            })
        
        response_data = {
            'success': True,
            'access': tokens['access'],
            'refresh': tokens['refresh'],
            'user': {
                'id': user.id,
                'telegram_id': user.telegram_id,
                'first_name': user.first_name,
                'username': user.username,
            },
            'contacts': contacts_data
        }
        
        response = JsonResponse(response_data)
        
        # Set cookies
        response.set_cookie('access_token', tokens['access'], max_age=7*24*60*60, path='/', samesite='Lax')
        response.set_cookie('refresh_token', tokens['refresh'], max_age=30*24*60*60, path='/', samesite='Lax')
        response.set_cookie('user_id', str(user.id), max_age=30*24*60*60, path='/', samesite='Lax')
        response.set_cookie('telegram_id', str(user.telegram_id), max_age=30*24*60*60, path='/', samesite='Lax')
        
        logger.info(f"✅ Auth success: {user}")
        return response
    
    except Exception as e:
        logger.error(f"❌ Auth error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def logout_api(request):
    """Logout - clear cookies and set offline"""
    logger.info("🚪 Logout requested")
    
    try:
        user_id = request.COOKIES.get('user_id')
        if user_id:
            try:
                user = Account.objects.get(id=user_id)
                user.is_online = False
                user.last_seen = timezone.now()
                user.save()
                logger.info(f"✅ User {user} set offline")
            except Account.DoesNotExist:
                pass
        
        response = JsonResponse({'success': True, 'message': 'Logged out'})
        
        response.delete_cookie('access_token', path='/')
        response.delete_cookie('refresh_token', path='/')
        response.delete_cookie('user_id', path='/')
        response.delete_cookie('telegram_id', path='/')
        
        return response
    
    except Exception as e:
        logger.error(f"❌ Logout error: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# ========================
# 🔍 SEARCH USERS
# ========================
@csrf_exempt
@require_http_methods(["POST"])
def search_users(request):
    """Search users by username, telegram_id, or first_name"""
    logger.info("🔍 Search users request")
    
    try:
        data = json.loads(request.body)
        search_type = data.get('type', 'username')
        search_value = data.get('value', '').strip()
        
        logger.info(f"Search type: {search_type}, value: '{search_value}'")
        
        if not search_value:
            return JsonResponse({
                'success': False, 
                'error': 'Search value required',
                'results': []
            }, status=400)
        
        user_id = request.COOKIES.get('user_id')
        
        # Build search query
        if search_type == 'username':
            # Remove @ if present
            if search_value.startswith('@'):
                search_value = search_value[1:]
            
            users = Account.objects.filter(
                Q(username__icontains=search_value) | 
                Q(first_name__icontains=search_value)
            )
        elif search_type == 'telegram_id':
            users = Account.objects.filter(telegram_id=search_value)
        else:
            users = Account.objects.filter(
                Q(username__icontains=search_value) | 
                Q(first_name__icontains=search_value)
            )
        
        # Exclude current user
        if user_id:
            users = users.exclude(id=user_id)
        
        # Limit results
        users = users[:10]
        
        logger.info(f"Found {users.count()} users")
        
        results = [{
            'id': u.id,
            'telegram_id': u.telegram_id,
            'username': u.username or f'user_{u.telegram_id}',
            'first_name': u.first_name,
            'last_name': u.last_name or '',
            'is_online': u.is_online,
            'bio': u.bio or '',
        } for u in users]
        
        logger.info(f"✅ Returning {len(results)} results")
        return JsonResponse({
            'success': True,
            'results': results,
            'total': len(results)
        })
    
    except Exception as e:
        logger.error(f"❌ Search error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e), 'results': []}, status=500)

# ========================
# 👥 CONTACTS
# ========================
@csrf_exempt
@require_http_methods(["POST"])
def add_contact(request):
    """Send contact request"""
    logger.info("➕ Add contact request")
    
    try:
        data = json.loads(request.body)
        user_id = request.COOKIES.get('user_id')
        contact_username = data.get('username')
        custom_name = data.get('custom_name', '')
        
        logger.info(f"User: {user_id}, Contact username: {contact_username}")
        
        if not user_id:
            return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
        
        if not contact_username:
            return JsonResponse({'success': False, 'error': 'Username required'}, status=400)
        
        try:
            user = Account.objects.get(id=user_id)
        except Account.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User not found'}, status=404)
        
        # Remove @ if present
        if contact_username.startswith('@'):
            contact_username = contact_username[1:]
        
        try:
            contact = Account.objects.get(username=contact_username)
        except Account.DoesNotExist:
            logger.warning(f"❌ Contact not found: {contact_username}")
            return JsonResponse({'success': False, 'error': 'User not found'}, status=404)
        
        if user.id == contact.id:
            return JsonResponse({'success': False, 'error': 'Cannot add yourself'}, status=400)
        
        # Check if already exists
        existing = Contact.objects.filter(user=user, contact=contact).first()
        if existing:
            if existing.is_accepted:
                return JsonResponse({'success': False, 'error': 'Already a contact'}, status=400)
            else:
                return JsonResponse({'success': False, 'error': 'Request already sent'}, status=400)
        
        # Create contact request
        contact_obj = Contact.objects.create(
            user=user,
            contact=contact,
            custom_name=custom_name or contact.first_name,
            is_accepted=False
        )
        
        logger.info(f"✅ Contact request created: {user} -> {contact}")
        return JsonResponse({
            'success': True,
            'message': 'Contact request sent',
            'contact': {
                'id': contact.id,
                'name': contact_obj.custom_name,
                'username': contact.username,
                'first_name': contact.first_name,
            }
        })
    
    except Exception as e:
        logger.error(f"❌ Add contact error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def accept_contact(request):
    """Accept contact request"""
    logger.info("✅ Accept contact request")
    
    try:
        data = json.loads(request.body)
        user_id = request.COOKIES.get('user_id')
        from_user_id = data.get('from_user_id')
        
        if not user_id or not from_user_id:
            return JsonResponse({'success': False, 'error': 'Missing IDs'}, status=400)
        
        # Find contact request (from_user sent request to current user)
        contact_request = Contact.objects.filter(
            user_id=from_user_id,
            contact_id=user_id,
            is_accepted=False
        ).first()
        
        if not contact_request:
            return JsonResponse({'success': False, 'error': 'Request not found'}, status=404)
        
        # Accept the request
        contact_request.is_accepted = True
        contact_request.accepted_at = timezone.now()
        contact_request.save()
        
        # Create reverse contact (so both can message each other)
        Contact.objects.get_or_create(
            user_id=user_id,
            contact_id=from_user_id,
            defaults={
                'is_accepted': True, 
                'accepted_at': timezone.now(),
                'custom_name': contact_request.user.first_name
            }
        )
        
        logger.info(f"✅ Contact accepted: {from_user_id} <-> {user_id}")
        return JsonResponse({'success': True, 'message': 'Contact accepted'})
    
    except Exception as e:
        logger.error(f"❌ Accept error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def reject_contact(request):
    """Reject contact request"""
    logger.info("❌ Reject contact request")
    
    try:
        data = json.loads(request.body)
        user_id = request.COOKIES.get('user_id')
        from_user_id = data.get('from_user_id')
        
        if not user_id or not from_user_id:
            return JsonResponse({'success': False, 'error': 'Missing IDs'}, status=400)
        
        # Find and delete contact request
        contact_request = Contact.objects.filter(
            user_id=from_user_id,
            contact_id=user_id,
            is_accepted=False
        ).first()
        
        if not contact_request:
            return JsonResponse({'success': False, 'error': 'Request not found'}, status=404)
        
        contact_request.delete()
        
        logger.info(f"✅ Contact rejected and deleted")
        return JsonResponse({'success': True, 'message': 'Request rejected'})
    
    except Exception as e:
        logger.error(f"❌ Reject error: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
def get_contacts(request):
    """Get user's contacts (accepted + pending requests)"""
    logger.info("📋 Get contacts")
    
    try:
        user_id = request.COOKIES.get('user_id')
        if not user_id:
            return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
        
        # Get accepted contacts
        accepted = Contact.objects.filter(
            user_id=user_id,
            is_accepted=True
        ).select_related('contact').order_by('-accepted_at')
        
        # Get pending requests TO this user (from others)
        pending_from_them = Contact.objects.filter(
            contact_id=user_id,
            is_accepted=False
        ).select_related('user').order_by('-created_at')
        
        # Get pending requests FROM this user (to others)
        pending_from_me = Contact.objects.filter(
            user_id=user_id,
            is_accepted=False
        ).select_related('contact').order_by('-created_at')
        
        contacts_data = []
        
        # Add accepted contacts
        for c in accepted:
            contacts_data.append({
                'id': c.contact.id,
                'user_id': c.user.id,
                'telegram_id': c.contact.telegram_id,
                'name': c.custom_name or c.contact.first_name,
                'username': c.contact.username,
                'is_online': c.contact.is_online,
                'last_seen': c.contact.last_seen.isoformat() if c.contact.last_seen else None,
                'is_accepted': True,
                'pending_from_them': False
            })
        
        # Add pending requests (FROM them TO me)
        for c in pending_from_them:
            contacts_data.append({
                'id': c.user.id,
                'user_id': c.user.id,
                'telegram_id': c.user.telegram_id,
                'name': c.custom_name or c.user.first_name,
                'username': c.user.username,
                'is_online': c.user.is_online,
                'last_seen': c.user.last_seen.isoformat() if c.user.last_seen else None,
                'is_accepted': False,
                'pending_from_them': True  # Show accept/reject buttons
            })
        
        # Add pending requests (FROM me TO them)
        for c in pending_from_me:
            contacts_data.append({
                'id': c.contact.id,
                'user_id': c.user.id,
                'telegram_id': c.contact.telegram_id,
                'name': c.custom_name or c.contact.first_name,
                'username': c.contact.username,
                'is_online': c.contact.is_online,
                'last_seen': c.contact.last_seen.isoformat() if c.contact.last_seen else None,
                'is_accepted': False,
                'pending_from_them': False  # Just show "Pending" badge
            })
        
        logger.info(f"✅ Found {len(contacts_data)} contacts/requests")
        return JsonResponse({'success': True, 'contacts': contacts_data})
    
    except Exception as e:
        logger.error(f"❌ Get contacts error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# ========================
# 💬 MESSAGES
# ========================
@csrf_exempt
@require_http_methods(["GET"])
def get_messages(request, contact_id):
    """Get messages with a specific contact"""
    logger.info(f"💬 Get messages with contact {contact_id}")
    
    try:
        user_id = request.COOKIES.get('user_id')
        if not user_id:
            return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
        
        # Get messages between user and contact
        messages = Message.objects.filter(
            Q(sender_id=user_id, receiver_id=contact_id) |
            Q(sender_id=contact_id, receiver_id=user_id)
        ).order_by('created_at')
        
        # Delete expired messages
        now = timezone.now()
        expired = messages.filter(expires_at__lt=now)
        expired_count = expired.count()
        if expired_count > 0:
            logger.info(f"🗑️ Deleting {expired_count} expired messages")
            expired.delete()
        
        # Get remaining messages
        messages = messages.filter(expires_at__gte=now)
        
        messages_data = [{
            'id': m.id,
            'content': m.text,
            'sender_id': m.sender_id,
            'is_read': m.is_read,
            'created_at': m.created_at.isoformat(),
            'expires_at': m.expires_at.isoformat(),
        } for m in messages]
        
        logger.info(f"✅ Found {len(messages_data)} messages")
        return JsonResponse({'success': True, 'messages': messages_data})
    
    except Exception as e:
        logger.error(f"❌ Get messages error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def send_message(request):
    """Send a message"""
    logger.info("📤 Send message")
    
    try:
        data = json.loads(request.body)
        user_id = request.COOKIES.get('user_id')
        to_user_id = data.get('to_user_id')
        content = data.get('content', '').strip()
        expire_seconds = data.get('expire_seconds', 86400)  # Default 24 hours
        
        if not user_id or not to_user_id or not content:
            return JsonResponse({'success': False, 'error': 'Missing fields'}, status=400)
        
        # Check if users are contacts
        contact_exists = Contact.objects.filter(
            user_id=user_id,
            contact_id=to_user_id,
            is_accepted=True
        ).exists()
        
        if not contact_exists:
            return JsonResponse({'success': False, 'error': 'Not a contact'}, status=403)
        
        # Create message
        expires_at = timezone.now() + timedelta(seconds=expire_seconds)
        message = Message.objects.create(
            sender_id=user_id,
            receiver_id=to_user_id,
            text=content,
            expires_at=expires_at
        )
        
        logger.info(f"✅ Message sent: {user_id} -> {to_user_id}")
        return JsonResponse({
            'success': True,
            'message': {
                'id': message.id,
                'content': message.text,
                'created_at': message.created_at.isoformat(),
                'expires_at': message.expires_at.isoformat()
            }
        })
    
    except Exception as e:
        logger.error(f"❌ Send message error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
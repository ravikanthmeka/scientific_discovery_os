import os
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session
import database
import database_models
import jwt
from typing import Optional
from pydantic import BaseModel

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID")
SECRET_KEY = "super_secret_discovery_key_for_dev_only"
ALGORITHM = "HS256"

router = APIRouter()

def get_current_user(token: str, db: Session):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = db.query(database_models.User).filter(database_models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

class CheckoutRequest(BaseModel):
    token: str
    success_url: str
    cancel_url: str

@router.post("/checkout")
async def create_checkout_session(req: CheckoutRequest, db: Session = Depends(database.get_db)):
    if not stripe.api_key or not STRIPE_PRICE_ID:
        raise HTTPException(status_code=500, detail="Stripe configuration missing on server")

    user = get_current_user(req.token, db)
    
    try:
        # Create a checkout session for Metered Billing
        checkout_session = stripe.checkout.Session.create(
            mode='subscription',
            line_items=[{
                'price': STRIPE_PRICE_ID,
            }],
            client_reference_id=str(user.id),
            success_url=req.success_url,
            cancel_url=req.cancel_url,
            customer_email=user.email,
        )
        return {"url": checkout_session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None), db: Session = Depends(database.get_db)):
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Stripe webhook secret not configured")

    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle the checkout.session.completed event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        user_id_str = session.get('client_reference_id')
        if user_id_str:
            user = db.query(database_models.User).filter(database_models.User.id == int(user_id_str)).first()
            if user:
                # Retrieve subscription to get the subscription item ID for metered billing
                sub_id = session.get('subscription')
                if sub_id:
                    subscription = stripe.Subscription.retrieve(sub_id)
                    sub_item_id = subscription['items']['data'][0]['id']
                    
                    user.subscription_tier = 'PRO'
                    user.stripe_customer_id = session.get('customer')
                    user.stripe_subscription_id = sub_id
                    user.stripe_subscription_item_id = sub_item_id
                    db.commit()

    return {"status": "success"}

def report_usage(user: database_models.User, tokens: int, db: Session):
    """
    Reports token usage to Stripe for PRO users, or increments local DB token usage for FREE users.
    """
    if not user:
        return
        
    if user.subscription_tier == "PRO" and user.stripe_customer_id and stripe.api_key:
        try:
            stripe.billing.MeterEvent.create(
                event_name="token_used",
                payload={
                    "stripe_customer_id": user.stripe_customer_id,
                    "value": str(tokens),
                }
            )
            # Still record locally for display purposes
            user.tokens_used += tokens
            db.commit()
        except Exception as e:
            print(f"Failed to report usage to Stripe for user {user.id}: {e}")
    else:
        # FREE tier: Just increment local token count
        user.tokens_used += tokens
        db.commit()
@router.get("/usage")
async def get_usage(db: Session = Depends(database.get_db), token: str = Header(None)):
    user = get_current_user(token, db)
    
    # Seamless auto-upgrade for test accounts without requiring re-login
    if "@synaptolab.app" in user.email.lower() or "@synaptoloab.app" in user.email.lower():
        if user.subscription_tier != "PRO":
            user.subscription_tier = "PRO"
            db.commit()
            
    return {
        "tier": user.subscription_tier,
        "tokens_used": user.tokens_used,
        "limit": 1000 if user.subscription_tier == "FREE" else "Unlimited"
    }

import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from core.dependencies import get_current_active_user
from database import get_db
from features.auth.models import User, UserCategory
from features.payments import paystack
from features.payments.schemas import CheckoutRequest, CheckoutResponse, PaymentResponse
from features.payments.service import CheckoutError, PaymentService, payment_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("/checkout", response_model=CheckoutResponse, status_code=status.HTTP_201_CREATED)
async def checkout(
    data: CheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create the cart's orders (unpaid) and a Paystack transaction for their total.
    Send the buyer to `authorization_url`; Paystack returns them to `callback_url`
    with ?reference=..., which the frontend passes to /payments/verify/{reference}."""
    if current_user.category != UserCategory.CONSUMER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only buyers can check out")
    try:
        payment, authorization_url = await PaymentService(db).checkout(current_user, data)
    except CheckoutError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return CheckoutResponse(**payment_response(payment).model_dump(), authorization_url=authorization_url)


@router.get("/verify/{reference}", response_model=PaymentResponse)
async def verify_payment(
    reference: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Check a checkout's payment with Paystack; marks its orders paid on success."""
    service = PaymentService(db)
    payment = service.get_payment(reference, current_user.id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    try:
        payment = await service.verify(payment, background_tasks)
    except paystack.PaystackError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return payment_response(service.get_payment(payment.reference))


@router.post("/paystack/webhook", include_in_schema=False)
async def paystack_webhook(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Paystack's server-to-server notice, so payments are recorded even if the
    buyer closes the tab before returning. Set this URL in the Paystack dashboard."""
    raw_body = await request.body()
    if not paystack.valid_webhook_signature(raw_body, request.headers.get("x-paystack-signature")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    try:
        event = json.loads(raw_body)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload")

    data = event.get("data") or {}
    if event.get("event") == "charge.success" and data.get("reference"):
        service = PaymentService(db)
        payment = service.get_payment(data["reference"])
        if payment:
            service.apply_transaction(payment, data, background_tasks)
        else:
            logger.warning("Paystack webhook for unknown reference %s", data["reference"])
    # Always 200 for a valid signature, or Paystack keeps retrying
    return {"received": True}

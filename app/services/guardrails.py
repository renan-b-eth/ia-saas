from datetime import datetime, timedelta
from app.constants import PLAN_LEVELS


def get_recommendations(company_name: str):
    name = (company_name or "").lower()
    if any(x in name for x in ["pizzaria", "restaurante", "hamburgueria", "café", "doce"]):
        return ["menu_eng", "waste", "delivery", "instavideo"]
    if any(x in name for x in ["loja", "roupa", "fashion", "boutique", "calcado"]):
        return ["persona", "instapost", "spy"]
    if any(x in name for x in ["barbearia", "salão", "estetica"]):
        return ["upsell", "localseo", "review_reply", "instavideo"]
    return ["instavideo", "promo", "persona"]


def get_effective_plan(user):
    # Backdoor do admin
    if getattr(user, "email", "") == "renanacademic21@gmail.com":
        return "agency"

    # Pagante
    if user.plan_tier in ["starter", "pro", "agency"]:
        return user.plan_tier

    # Trial 14 dias -> PRO
    if user.created_at:
        dias_de_vida = (datetime.utcnow() - user.created_at).days
        if dias_de_vida < 14:
            return "pro"

    return "free"


def get_trial_days_left(user):
    if user.plan_tier != "free":
        return 0
    if not user.created_at:
        return 0
    dias = (datetime.utcnow() - user.created_at).days
    restante = 14 - dias
    return max(0, restante)


def user_can_access(user, tool_min_plan: str):
    effective_plan = get_effective_plan(user)
    u_level = PLAN_LEVELS.get(effective_plan, 0)
    t_level = PLAN_LEVELS.get(tool_min_plan, 0)
    return u_level >= t_level

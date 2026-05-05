"""临床自动计算：MAP、氧合指数、出入量平衡、术后日数"""

from datetime import date, datetime


def calc_map(sys_bp: float, dia_bp: float) -> float | None:
    """平均动脉压 MAP = (SBP + 2*DBP) / 3"""
    if sys_bp is None or dia_bp is None:
        return None
    return round((sys_bp + 2 * dia_bp) / 3, 1)


def calc_oi(pao2: float, fio2: float) -> float | None:
    """氧合指数 = PaO2 / FiO2（FiO2需为小数，如60%→0.6）"""
    if pao2 is None or fio2 is None or fio2 == 0:
        return None
    fio2_decimal = fio2 / 100 if fio2 > 1 else fio2
    return round(pao2 / fio2_decimal, 1)


def calc_balance(intake: float, output: float) -> float | None:
    """出入量平衡"""
    if intake is None or output is None:
        return None
    return round(intake - output, 0)


def calc_postop_days(surgery_date_str: str | None) -> int | None:
    """术后日数 = 当前日期 - 手术日期"""
    if not surgery_date_str:
        return None
    try:
        surgery_date = date.fromisoformat(surgery_date_str)
        return (date.today() - surgery_date).days
    except (ValueError, TypeError):
        return None


def check_critical(key: str, value: float) -> tuple[bool, str]:
    """检查是否为危急值，返回 (是否危急, 标签)"""
    if value is None:
        return False, ""

    thresholds = {
        "abg_lac": (None, 2, None, "乳酸 >2 mmol/L ⚠️"),
        "ionized_ca": (1.15, None, None, "离子钙 <1.15 mmol/L ⚠️"),
        "abg_ph": (7.25, 7.55, "both", "pH 危急值 ⚠️"),
        "d_dimer": (None, 3000, None, "D-二聚体 >3000 ng/mL ⚠️"),
    }

    if key not in thresholds:
        return False, ""

    lo, hi, mode, label = thresholds[key]

    if mode == "both":
        if (lo is not None and value < lo) or (hi is not None and value > hi):
            return True, label
    else:
        if lo is not None and value < lo:
            return True, label
        if hi is not None and value > hi:
            return True, label

    return False, ""

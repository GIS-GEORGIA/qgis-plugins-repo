"""
Wind მოდული — აქ არის ნამდვილი ინჟინერია (ღიად არსად ინტეგრირებული).

ჯაჭვი:  სადგურები → [interpolation | windninja] → ქარის ველი
         → weibull (fit) → power_curve → AEP (წლიური ენერგია) → ₾

weibull.py + power_curve.py  — pure math, მუშა (MVP).
interpolation.py             — IDW/Kriging + სიმაღლური კორექცია.
windninja_backend.py         — WindNinja CLI wrapper (გარე ბინარი).
"""
__all__ = ["weibull", "power_curve", "interpolation", "windninja_backend"]

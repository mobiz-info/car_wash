#!/usr/bin/env python3
"""
Seed all countries from the Flutter app into the backend Country model.
Run: python3 seed_countries.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wash_pilot.settings')
django.setup()

from master.models import Country

COUNTRIES = [
    {'name': 'India', 'phone_iso_code': 'IN', 'phone_dial_code': '+91', 'currency_symbol': '₹', 'currency_code': 'INR', 'flag': '🇮🇳', 'locale_tag': 'en_IN'},
    {'name': 'Saudi Arabia', 'phone_iso_code': 'SA', 'phone_dial_code': '+966', 'currency_symbol': 'SAR', 'currency_code': 'SAR', 'flag': '🇸🇦', 'locale_tag': 'ar_SA'},
    {'name': 'United Arab Emirates', 'phone_iso_code': 'AE', 'phone_dial_code': '+971', 'currency_symbol': 'AED', 'currency_code': 'AED', 'flag': '🇦🇪', 'locale_tag': 'ar_AE'},
    {'name': 'Kuwait', 'phone_iso_code': 'KW', 'phone_dial_code': '+965', 'currency_symbol': 'KWD', 'currency_code': 'KWD', 'flag': '🇰🇼', 'locale_tag': 'ar_KW'},
    {'name': 'Qatar', 'phone_iso_code': 'QA', 'phone_dial_code': '+974', 'currency_symbol': 'QAR', 'currency_code': 'QAR', 'flag': '🇶🇦', 'locale_tag': 'ar_QA'},
    {'name': 'Bahrain', 'phone_iso_code': 'BH', 'phone_dial_code': '+973', 'currency_symbol': 'BHD', 'currency_code': 'BHD', 'flag': '🇧🇭', 'locale_tag': 'ar_BH'},
    {'name': 'Oman', 'phone_iso_code': 'OM', 'phone_dial_code': '+968', 'currency_symbol': 'OMR', 'currency_code': 'OMR', 'flag': '🇴🇲', 'locale_tag': 'ar_OM'},
    {'name': 'United States', 'phone_iso_code': 'US', 'phone_dial_code': '+1', 'currency_symbol': '$', 'currency_code': 'USD', 'flag': '🇺🇸', 'locale_tag': 'en_US'},
    {'name': 'United Kingdom', 'phone_iso_code': 'GB', 'phone_dial_code': '+44', 'currency_symbol': '£', 'currency_code': 'GBP', 'flag': '🇬🇧', 'locale_tag': 'en_GB'},
    {'name': 'Vietnam', 'phone_iso_code': 'VN', 'phone_dial_code': '+84', 'currency_symbol': '₫', 'currency_code': 'VND', 'flag': '🇻🇳', 'locale_tag': 'vi_VN'},
    {'name': 'Thailand', 'phone_iso_code': 'TH', 'phone_dial_code': '+66', 'currency_symbol': '฿', 'currency_code': 'THB', 'flag': '🇹🇭', 'locale_tag': 'th_TH'},
    {'name': 'Russia', 'phone_iso_code': 'RU', 'phone_dial_code': '+7', 'currency_symbol': '₽', 'currency_code': 'RUB', 'flag': '🇷🇺', 'locale_tag': 'ru_RU'},
    {'name': 'China', 'phone_iso_code': 'CN', 'phone_dial_code': '+86', 'currency_symbol': '¥', 'currency_code': 'CNY', 'flag': '🇨🇳', 'locale_tag': 'zh_CN'},
    {'name': 'Ghana', 'phone_iso_code': 'GH', 'phone_dial_code': '+233', 'currency_symbol': 'GH₵', 'currency_code': 'GHS', 'flag': '🇬🇭', 'locale_tag': 'en_GH'},
    {'name': 'Benin', 'phone_iso_code': 'BJ', 'phone_dial_code': '+229', 'currency_symbol': 'CFA', 'currency_code': 'XOF', 'flag': '🇧🇯', 'locale_tag': 'fr_BJ'},
    {'name': 'Ivory Coast', 'phone_iso_code': 'CI', 'phone_dial_code': '+225', 'currency_symbol': 'CFA', 'currency_code': 'XOF', 'flag': '🇨🇮', 'locale_tag': 'fr_CI'},
]

def get_next_auto_id():
    last = Country.objects.order_by('-auto_id').first()
    return (last.auto_id + 1) if last else 1

def seed_countries():
    print("Seeding countries...\n")
    created = 0
    updated = 0
    for data in COUNTRIES:
        obj = Country.objects.filter(phone_iso_code=data['phone_iso_code']).first()
        if not obj:
            if data['phone_iso_code'] == 'AE':
                obj = Country.objects.filter(name__in=['UAE', 'United Arab Emirates']).first()
            elif data['phone_iso_code'] == 'US':
                obj = Country.objects.filter(name__in=['United States', 'USA']).first()
            elif data['phone_iso_code'] == 'GB':
                obj = Country.objects.filter(name__in=['United Kingdom', 'UK']).first()
            else:
                obj = Country.objects.filter(name__iexact=data['name']).first()

        if obj:
            for k, v in data.items():
                setattr(obj, k, v)
            obj.save()
            print(f"  Updated: {data['flag']} {data['name']} ({data['phone_iso_code']})")
            updated += 1
        else:
            Country.objects.create(auto_id=get_next_auto_id(), **data)
            print(f"  Created: {data['flag']} {data['name']} ({data['phone_iso_code']})")
            created += 1
    print(f"\nDone! {created} created, {updated} updated.")

if __name__ == '__main__':
    seed_countries()

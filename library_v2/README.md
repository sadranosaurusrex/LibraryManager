# کتاب‌خانهٔ من — Library Studio v2

پروژهٔ موازی مدیریت کتابخانهٔ شخصی با تمرکز بر تجربهٔ کاربری فارسی (RTL)، تقویم جلالی، جستجوی هوشمند فارسی، نقشهٔ فیزیکی کمدها و قفسه‌ها، آمار تحلیلی و مرکز سلامت داده‌های اکسل — با حفظ سازگاری کامل با فایل `data/Books_v2.xlsx` و پشتیبانی از زبان انگلیسی.

## اجرای برنامه

از ریشهٔ مخزن (`d:\LibraryManager`):

```powershell
C:/Python314/python.exe library_v2/run.py
```

### گزینه‌های اجرایی
- `--data path/to/Books_v2.xlsx` : مسیر فایل اکسل دلخواه
- `--port 8765` : پورت سرور محلی
- `--browser-mode app|tab` : اجرا به‌صورت پنجرهٔ مستقل دسکتاپ (`app`) یا تب مرورگر (`tab`)
- `--no-browser` : اجرای سرور بدون باز کردن خودکار مرورگر

## اجرای تست‌ها

```powershell
C:/Python314/python.exe -m unittest discover -s library_v2/tests -v
```

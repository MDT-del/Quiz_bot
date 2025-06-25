<?php
// فعال کردن نمایش خطاها برای دیباگ
ini_set('display_errors', 1);
ini_set('display_startup_errors', 1);
error_reporting(E_ALL);

require '../vendor/autoload.php';

use Zarinpal\Zarinpal;

// خواندن اطلاعات از URL
$userId = filter_input(INPUT_GET, 'user_id', FILTER_SANITIZE_NUMBER_INT);
$amount = filter_input(INPUT_GET, 'amount', FILTER_SANITIZE_NUMBER_INT);
$orderId = filter_input(INPUT_GET, 'order_id', FILTER_SANITIZE_STRING); // این همان authority است
$duration = filter_input(INPUT_GET, 'duration', FILTER_SANITIZE_NUMBER_INT); // خواندن مدت زمان

// خواندن تنظیمات از متغیرهای محیطی
$merchantCode = getenv('ZARINPAL_MERCHANT_CODE');
$replitAppUrl = rtrim(getenv('REPLIT_APP_URL'), '/'); // حذف اسلش اضافه از انتهای آدرس

if (!$userId || !$amount || !$orderId || !$merchantCode || !$replitAppUrl || !$duration) { // بررسی duration هم اضافه شد
    header("Content-Type: text/html; charset=UTF-8");
    die("<h1>خطا: اطلاعات ارسالی ناقص است (کد ۱). لطفاً از طریق ربات اقدام کنید.</h1>");
}

// آدرس بازگشت باید به اسکریپت verify.php اشاره کند و شامل مدت زمان هم باشد
$callbackUrl = $replitAppUrl . '/payment/verify.php?order_id=' . $orderId . '&amount=' . $amount . '&duration=' . $duration;

try {
    $zarinpal = new Zarinpal($merchantCode);
    $payment = $zarinpal->request(
        $callbackUrl,
        $amount,
        "خرید اشتراک ویژه ربات"
    );

    if ($payment->success()) {
        $paymentUrl = $payment->getPaymentUrl();
        header('Location: ' . $paymentUrl);
        exit();
    } else {
        header("Content-Type: text/html; charset=UTF-8");
        echo "<h1>خطا در اتصال به درگاه پرداخت</h1>";
        echo "<p>کد خطا: " . htmlspecialchars($payment->getError()) . "</p>";
    }

} catch (Exception $e) {
    header("Content-Type: text/html; charset=UTF-8");
    die('<h1>خطای پیش‌بینی نشده در سیستم پرداخت: </h1>' . $e->getMessage());
}

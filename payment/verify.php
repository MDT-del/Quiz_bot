<?php
ini_set('display_errors', 1);
error_reporting(E_ALL);

require '../vendor/autoload.php';

use Zarinpal\Zarinpal;

// خواندن اطلاعات از URL که زرین‌پال و اسکریپت قبلی فرستاده‌اند
$authority = filter_input(INPUT_GET, 'Authority', FILTER_SANITIZE_STRING);
$status = filter_input(INPUT_GET, 'Status', FILTER_SANITIZE_STRING);
$orderId = filter_input(INPUT_GET, 'order_id', FILTER_SANITIZE_STRING); // authority اولیه از سیستم ما
$amount = filter_input(INPUT_GET, 'amount', FILTER_SANITIZE_NUMBER_INT);
$duration = filter_input(INPUT_GET, 'duration', FILTER_SANITIZE_NUMBER_INT); // خواندن مدت زمان از callback

// خواندن تنظیمات از متغیرهای محیطی
$merchantCode = getenv('ZARINPAL_MERCHANT_CODE');
$replitAppUrl = rtrim(getenv('REPLIT_APP_URL'), '/');
$phpSecretKey = getenv('PHP_SECRET_KEY');

if (!$authority || !$status || !$orderId || !$merchantCode || !$replitAppUrl || !$phpSecretKey || !$amount || !$duration) { // بررسی duration هم اضافه شد
    header("Content-Type: text/html; charset=UTF-8");
    die("<h1>خطا: اطلاعات بازگشتی از درگاه ناقص است (کد ۲).</h1>");
}

$flaskFailureUrl = $replitAppUrl . "/payment-failed";
$flaskSuccessPageUrl = $replitAppUrl . "/payment-success";

if ($status !== 'OK') {
    // پرداخت توسط کاربر لغو شده است
    header('Location: ' . $flaskFailureUrl . '?reason=cancelled');
    exit();
}

try {
    $zarinpal = new Zarinpal($merchantCode);
    $verification = $zarinpal->verify('OK', $amount, $authority);

    if ($verification->success()) {
        $refId = $verification->getReferenceId();

        // حالا نتیجه را به سرور پایتون اطلاع می‌دهیم
        $flaskCallbackUrl = $replitAppUrl . '/api/php/payment-callback';
        
        $postData = json_encode([
            'order_id' => $orderId, // این همان authority است که در دیتابیس ذخیره شده
            'status' => 'completed',
            'ref_id' => $refId,
            'amount' => $amount,
            'duration' => $duration // اضافه کردن مدت زمان به داده‌های ارسالی
        ]);

        $ch = curl_init($flaskCallbackUrl);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, $postData);
        curl_setopt($ch, CURLOPT_HTTPHEADER, [
            'Content-Type: application/json',
            'Content-Length: ' . strlen($postData),
            'Authorization: Bearer ' . $phpSecretKey // ارسال کلید مخفی برای امنیت
        ]);

        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        
        // اگر سرور پایتون تایید کرد، کاربر را به صفحه موفقیت بفرست
        if ($httpCode == 200) {
            header('Location: ' . $flaskSuccessPageUrl . '?ref_id=' . $refId);
            exit();
        } else {
             // اگر سرور پایتون تایید نکرد، این یک خطای جدی است و باید لاگ شود
             error_log("Failed to notify Flask server. HTTP Code: $httpCode. Response: $response");
             header("Content-Type: text/html; charset=UTF-8");
             die("<h1>خطای داخلی</h1><p>پرداخت شما انجام شد اما در ثبت آن در ربات مشکلی پیش آمده است. لطفاً با پشتیبانی تماس بگیرید. شماره پیگیری: $refId</p>");
        }

    } else {
        // اگر تاییدیه زرین‌پال ناموفق بود
        $error = $verification->getError();
        header('Location: ' . $flaskFailureUrl . '?reason=verification_failed&error=' . urlencode($error));
        exit();
    }

} catch (Exception $e) {
    header("Content-Type: text/html; charset=UTF-8");
    die('<h1>خطای پیش‌بینی نشده در سیستم تایید پرداخت: </h1>' . $e->getMessage());
}

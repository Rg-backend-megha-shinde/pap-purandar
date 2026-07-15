(function () {
    window.MockBiometricAdapter = {
        async capture(config) {
            const capturedAt = new Date().toISOString();
            return {
                success: true,
                fingerprintImage: null,
                fingerprintTemplate: 'MOCK_FINGERPRINT_TEMPLATE',
                quality: Math.max(Number(config?.minQuality) || 60, 85),
                deviceId: 'MOCK-DEVICE',
                provider: 'mock',
                capturedAt,
                message: 'Mock fingerprint captured. Replace with actual biometric device integration later.',
            };
        },
    };
})();

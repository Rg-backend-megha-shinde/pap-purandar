(function () {
    window.GenericHttpBiometricAdapter = {
        async capture(config) {
            if (!config?.captureUrl) {
                throw new Error('Biometric capture URL is not configured.');
            }
            const response = await fetch(config.captureUrl, {
                method: config.method || 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(config.headers || {}),
                },
                body: JSON.stringify(config.payload || {}),
            });
            if (!response.ok) {
                throw new Error(`Biometric device returned HTTP ${response.status}.`);
            }
            const data = await response.json();
            return {
                success: Boolean(data.success ?? true),
                fingerprintImage: data.fingerprintImage || data.fingerprint_image || null,
                fingerprintTemplate: data.fingerprintTemplate || data.fingerprint_template || data.template || null,
                pidData: data.pidData || data.pid_data || data.pid || null,
                quality: data.quality ?? data.qualityScore ?? null,
                deviceId: data.deviceId || data.device_id || null,
                provider: 'generic_http',
                capturedAt: data.capturedAt || data.captured_at || new Date().toISOString(),
                message: data.message || 'Fingerprint captured from generic HTTP biometric adapter.',
            };
        },
    };
})();

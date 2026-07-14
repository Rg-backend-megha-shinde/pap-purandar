(function () {
    function normalizeBiometricResponse(result, provider) {
        return {
            success: Boolean(result?.success),
            fingerprintImage: result?.fingerprintImage || null,
            fingerprintTemplate: result?.fingerprintTemplate || null,
            pidData: result?.pidData || null,
            quality: result?.quality ?? null,
            deviceId: result?.deviceId || null,
            provider: result?.provider || provider || 'mock',
            capturedAt: result?.capturedAt || new Date().toISOString(),
            status: result?.success ? 'captured' : 'failed',
            message: result?.message || '',
        };
    }

    window.captureFingerprint = async function captureFingerprint(configOverride) {
        const config = {
            provider: 'mock',
            captureUrl: 'http://127.0.0.1:11100/capture',
            minQuality: 60,
            ...(window.BIOMETRIC_CONFIG || {}),
            ...(configOverride || {}),
        };
        const provider = config.provider || 'mock';
        const adapter = provider === 'mantra_mfs110'
            ? window.MantraMfs110Adapter
            : provider === 'generic_http'
                ? window.GenericHttpBiometricAdapter
                : window.MockBiometricAdapter;

        if (!adapter?.capture) {
            throw new Error(`Biometric provider "${provider}" is not available.`);
        }

        const result = await adapter.capture(config);
        const normalized = normalizeBiometricResponse(result, provider);
        const hasQuality = normalized.quality !== null && normalized.quality !== undefined && String(normalized.quality).trim() !== '';
        const quality = Number(normalized.quality);
        if (normalized.success && hasQuality && Number.isFinite(quality) && quality < Number(config.minQuality || 0)) {
            return {
                ...normalized,
                success: false,
                status: 'failed',
                message: `Fingerprint quality ${quality} is below minimum ${config.minQuality}.`,
            };
        }
        return normalized;
    };
})();

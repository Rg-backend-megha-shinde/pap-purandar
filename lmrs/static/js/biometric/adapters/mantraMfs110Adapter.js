(function () {
    const DEFAULT_RD_SERVICE_URL = 'http://127.0.0.1:11100';
    const DEFAULT_PID_OPTIONS = '<PidOptions ver="1.0"><Opts fCount="1" fType="2" iCount="0" pCount="0" format="0" pidVer="2.0" timeout="10000" posh="UNKNOWN" env="P" /></PidOptions>';

    function uniqueValues(values) {
        return Array.from(new Set(values.filter(Boolean).map((value) => String(value).replace(/\/+$/, ''))));
    }

    function getOriginFromUrl(url) {
        try {
            return new URL(url).origin;
        } catch (error) {
            return '';
        }
    }

    function joinUrl(baseUrl, path) {
        if (!path) return baseUrl;
        if (/^https?:\/\//i.test(path)) return path;
        return `${String(baseUrl || '').replace(/\/+$/, '')}/${String(path).replace(/^\/+/, '')}`;
    }

    async function fetchTextWithTimeout(url, options = {}, timeoutMs = 5000) {
        const controller = new AbortController();
        const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
        try {
            const response = await fetch(url, {
                ...options,
                signal: controller.signal,
            });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return {
                response,
                text: await response.text(),
            };
        } finally {
            window.clearTimeout(timeoutId);
        }
    }

    function extractXmlAttribute(xmlDocument, selectors, attributeNames) {
        for (const selector of selectors) {
            const node = xmlDocument.querySelector(selector);
            if (!node) continue;
            for (const attributeName of attributeNames) {
                const value = node.getAttribute(attributeName);
                if (value !== null && value !== undefined && String(value).trim()) {
                    return String(value).trim();
                }
            }
        }
        return null;
    }

    function extractXmlText(xmlDocument, selectors) {
        for (const selector of selectors) {
            const node = xmlDocument.querySelector(selector);
            const value = node?.textContent;
            if (value !== null && value !== undefined && String(value).trim()) {
                return String(value).trim();
            }
        }
        return null;
    }

    function parseXmlResponse(rawText) {
        const parser = new DOMParser();
        const xmlDocument = parser.parseFromString(rawText, 'application/xml');
        if (xmlDocument.querySelector('parsererror')) {
            throw new Error('Invalid response received from Mantra fingerprint service.');
        }

        const errorCode = extractXmlAttribute(xmlDocument, ['Resp', 'resp'], ['errCode', 'errcode', 'code']);
        const errorInfo = extractXmlAttribute(xmlDocument, ['Resp', 'resp'], ['errInfo', 'errinfo', 'message']);
        const qualityValue = extractXmlAttribute(xmlDocument, ['Resp', 'resp', 'Quality', 'quality'], ['qScore', 'qscore', 'quality']);
        const deviceId = extractXmlAttribute(xmlDocument, ['DeviceInfo', 'DeviceInfo > additional_info', 'Param'], ['dc', 'dpId', 'mi', 'mc', 'value'])
            || extractXmlText(xmlDocument, ['DeviceInfo', 'DeviceId', 'DeviceSerialNumber']);
        const biometricData = extractXmlText(xmlDocument, ['Data', 'PidData', 'Bios', 'Bio']);
        const success = !errorCode || errorCode === '0';

        return {
            success,
            fingerprintImage: null,
            fingerprintTemplate: null,
            pidData: rawText,
            quality: qualityValue !== null ? qualityValue : null,
            deviceId,
            provider: 'mantra_mfs110',
            capturedAt: new Date().toISOString(),
            message: success
                ? 'Thumb impression captured successfully.'
                : (errorInfo || 'Fingerprint capture failed. Please retry.'),
            biometricDataPresent: Boolean(biometricData),
        };
    }

    function parseCapturePathFromRdService(rawText) {
        const parser = new DOMParser();
        const xmlDocument = parser.parseFromString(rawText, 'application/xml');
        if (xmlDocument.querySelector('parsererror')) {
            return '';
        }
        const interfaces = Array.from(xmlDocument.querySelectorAll('Interface'));
        const captureInterface = interfaces.find((node) => String(node.getAttribute('id') || '').toUpperCase() === 'CAPTURE');
        return captureInterface?.getAttribute('path') || '';
    }

    async function discoverCaptureUrl(config, timeoutMs) {
        if (config.skipDiscovery && config.captureUrl) {
            return config.captureUrl;
        }

        const baseUrls = uniqueValues([
            config.rdServiceUrl,
            getOriginFromUrl(config.captureUrl),
            DEFAULT_RD_SERVICE_URL,
        ]);

        for (const baseUrl of baseUrls) {
            try {
                const { text } = await fetchTextWithTimeout(baseUrl, { method: config.discoveryMethod || 'RDSERVICE' }, Math.min(timeoutMs, 5000));
                const capturePath = parseCapturePathFromRdService(text);
                if (capturePath) {
                    return joinUrl(baseUrl, capturePath);
                }
            } catch (error) {
                console.warn('Mantra RD discovery failed:', { baseUrl, message: error?.message || String(error) });
            }
        }

        return config.captureUrl || joinUrl(DEFAULT_RD_SERVICE_URL, '/rd/capture');
    }

    function normalizeJsonResponse(data) {
        const success = Boolean(data.success ?? data.status === 'success' ?? true);
        return {
            success,
            fingerprintImage: data.fingerprintImage || data.fingerprint_image || data.image || null,
            fingerprintTemplate: data.fingerprintTemplate || data.fingerprint_template || data.template || null,
            pidData: data.pidData || data.pid_data || data.pid || data.xml || null,
            quality: data.quality ?? data.qualityScore ?? data.qScore ?? null,
            deviceId: data.deviceId || data.device_id || data.serialNumber || data.serial_number || null,
            provider: 'mantra_mfs110',
            capturedAt: data.capturedAt || data.captured_at || new Date().toISOString(),
            message: data.message || (success ? 'Thumb impression captured successfully.' : 'Fingerprint capture failed. Please retry.'),
        };
    }

    function getUserFriendlyError(error) {
        const message = String(error?.message || '').toLowerCase();
        if (message.includes('failed to fetch') || message.includes('networkerror') || message.includes('load failed')) {
            return 'Mantra RD service is not reachable. Confirm the device is connected and the local service is running.';
        }
        if (message.includes('timeout')) {
            return 'Fingerprint capture timed out. Please place thumb again and retry.';
        }
        if (message.includes('cors')) {
            return 'Browser blocked the Mantra local service request. Please check RD service/browser permissions.';
        }
        return error?.message || 'Unable to capture thumb impression. Please retry.';
    }

    window.MantraMfs110Adapter = {
        async capture(config = {}) {
            const timeoutMs = Number(config.timeoutMs || config.timeout || 15000);
            const controller = new AbortController();
            if (config.signal?.aborted) {
                controller.abort();
            } else if (config.signal?.addEventListener) {
                config.signal.addEventListener('abort', () => controller.abort(), { once: true });
            }
            const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);

            try {
                const captureUrl = await discoverCaptureUrl(config, timeoutMs);
                const response = await fetch(captureUrl, {
                    method: config.method || 'CAPTURE',
                    headers: {
                        'Content-Type': config.contentType || 'text/xml; charset=utf-8',
                        ...(config.headers || {}),
                    },
                    body: config.payload || config.pidOptions || DEFAULT_PID_OPTIONS,
                    signal: controller.signal,
                });

                if (!response.ok) {
                    throw new Error(`Mantra fingerprint service returned HTTP ${response.status}.`);
                }

                const rawText = await response.text();
                const contentType = response.headers.get('content-type') || '';
                if (contentType.includes('application/json')) {
                    return normalizeJsonResponse(JSON.parse(rawText));
                }

                const trimmed = rawText.trim();
                if (trimmed.startsWith('{')) {
                    return normalizeJsonResponse(JSON.parse(trimmed));
                }
                if (trimmed.startsWith('<')) {
                    return parseXmlResponse(trimmed);
                }

                throw new Error('Invalid response received from Mantra fingerprint service.');
            } catch (error) {
                if (error?.name === 'AbortError') {
                    return {
                        success: false,
                        provider: 'mantra_mfs110',
                        capturedAt: new Date().toISOString(),
                        message: config.signal?.aborted
                            ? 'Fingerprint capture cancelled.'
                            : 'Fingerprint capture timed out. Please place thumb again and retry.',
                    };
                }
                return {
                    success: false,
                    provider: 'mantra_mfs110',
                    capturedAt: new Date().toISOString(),
                    message: getUserFriendlyError(error),
                };
            } finally {
                window.clearTimeout(timeoutId);
            }
        },
    };
})();

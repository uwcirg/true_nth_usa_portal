/*** wrapper object to initalize i18next ***/
var __i18next = window.__i18next = (function() {
    function init(options, callback) {
        var getQueryString = (function(a) {
            if (String(a) === "") { return {}; }
            var b = {};
            for (var i = 0; i < a.length; ++i) {
                var p = a[i].split("=", 2);
                if (p.length === 1) {
                    b[p[0]] = "";
                }
                else {
                    b[p[0]] = decodeURIComponent(p[1].replace(/\+/g, " "));
                }
            }
            return b;
        })(window.location.search.substr(1).split("&"));

        if (typeof window.localStorage !== "undefined") {
            if (window.localStorage.getItem("i18nextLng")) {
                window.localStorage.removeItem("i18nextLng");
            }
        }
        var source = options.loadPath ? options.loadPath : "/static/files/locales/{{lng}}/translation.json"; //consuming translation json from each corresponding locale
        var defaultOptions = {
            fallbackLng: "en-US",
            lng: "en-US",
            preload: false,
            debug: false,
            defaultNS: "translation",
            initImmediate: false,
            keySeparator: "----",
            nsSeparator: "----",
            load: "currentOnly",
            returnEmptyString: false,
            returnNull: false,
            saveMissing: false,
            missingKeyHandler: false,
            parseMissingKeyHandler: function(key) { //allow lookup for translated text for missing key
                var sessionData = sessionStorage.getItem("i18nextData_" + this.lng);
                if (!sessionData) {
                    return key;
                }
                try {
                    var data = JSON.parse(sessionData);
                    if (data && data.hasOwnProperty(key)) {
                        return data[key];
                    }
                } catch (e) {
                    return key;
                }
                return key;
            },
            backend: {
                // load from static file
                language: options.lng,
                loadPath: source,
                ajax: function(url, options, callback, data, cache) {
                    /*
                     * default code from i18nextBackend.js, but modify it to allow sync loading of resources and add session storage
                     */
                    if (options.language === "en-US") {
                        return false;
                    }
                    callback = callback || function() {};
                    var sessionItemKey = "i18nextData_" + options.language;
                    if (data && (typeof data === "undefined" ? "undefined" : _typeof(data)) === "object") { /*global _typeof */
                        if (!cache) { data["_t"] = new Date();}
                        // URL encoded form data must be in querystring format
                        data = addQueryString("", data).slice(1); /* global addQueryString */
                    }
                    if (options.queryStringParams) {
                        url = addQueryString(url, options.queryStringParams); /* global addQueryString */
                    }
                    try {
                        var x;
                        if (XMLHttpRequest) {
                            x = new XMLHttpRequest();
                        } else {
                            x = new ActiveXObject("MSXML2.XMLHTTP.3.0"); /*global ActiveXObject */
                        }
                        //use sync
                        x.open(data ? "POST" : "GET", url, 0);
                        if (!options.crossDomain) {
                            x.setRequestHeader("X-Requested-With", "XMLHttpRequest");
                        }
                        x.withCredentials = !!options.withCredentials;
                        if (data) {
                            x.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
                        }
                        if (x.overrideMimeType) {
                            x.overrideMimeType("application/json");
                        }
                        var h = options.customHeaders;
                        if (h) {
                            for (var i in h) {
                                if (h.hasOwnProperty(i)) {
                                    x.setRequestHeader(i, h[i]);
                                }
                            }
                        }
                        x.onreadystatechange = function() {
                            if (x.readyState > 3) {
                                callback(x.responseText, x);
                                if (x.responseText && !sessionStorage.getItem(sessionItemKey)) {
                                    sessionStorage.setItem(sessionItemKey, JSON.stringify(x.responseText));
                                }
                            }
                        };
                        x.send(data);
                    } catch (e) {
                        if (console) { console.log(e); }/*global console */
                    }
                }
            }
        };
        options = options || defaultOptions;
        if (options.lng) {
            options.lng = options.lng.replace("_", "-");
        }
        options.debug = options.debug ? options.debug : (getQueryString.debugi18next ? true : false);
        var configOptions = $.extend({}, defaultOptions, options); /*global $ */
        i18next.use(i18nextXHRBackend).init(configOptions, function(err, t) { /* global i18next i18nextXHRBackend */
            if (callback) {callback(t);}
        });
    }
    return {
        init: function(options, callback) {
            init(options, callback);
        }
    };
})();

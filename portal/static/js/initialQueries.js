(function() { /*global $ hasValue disableHeaderFooterLinks __convertToNumericField*/
    var FieldsChecker = function(dependencies) { //helper class to keep track of missing fields based on required/needed core data
        this.__getDependency = function(key) {
            if (key && this.dependencies.hasOwnProperty(key)) {
                return this.dependencies[key];
            } else {
                //should show up in console
                throw new Error("Dependency with key value: " + key + " not found.");
            }
        };
        this.userId = null;
        this.roleRequired = false;
        this.userRoles = [];
        this.CONFIG_REQUIRED_CORE_DATA = null;
        this.preselectClinic = "";
        this.defaultSections = {};
        this.mainSections = {};
        this.dependencies = dependencies || {};
        this.orgTool = null;
        this.ACCEPT_ON_NEXT = false;

    };

    FieldsChecker.prototype.init = function(callback) {
        var self = this;
        this.setUserId(function() {
            if (!self.userId) {
                alert("User id is required");
                return false;
            }
            self.initConfig(function(data) {
                self.preselectClinic = $("#preselectClinic").val();
                self.initSections();
                self.initSectionData();
                if (callback) {
                    callback(data);
                }
            });
        });
    };

    FieldsChecker.prototype.setUserId = function(callback) {
        var self = this, tnthAjax = this.__getDependency("tnthAjax");
        callback = callback || function() {};
        self.userId = $("#iq_userId").val(); //set in template, check this first as API can return error
        if (self.userId) {
            callback();
            return;
        }
        tnthAjax.getCurrentUser(function(data) {
            if (data && data.id) {
                self.userId = data.id;
            }
            callback();
        });
    };

    FieldsChecker.prototype.getOrgTool = function() {
        if (!this.orgTool) {
            this.orgTool = this.__getDependency("orgTool");
            this.orgTool.init();
        }
        return this.orgTool;
    };

    FieldsChecker.prototype.setSectionDataLoadedFlag = function(sectionId, flag) {
        if (!sectionId || !this.mainSections.hasOwnProperty(sectionId)) {
            return false;
        }
        this.mainSections[sectionId].loaded = flag;
    };

    FieldsChecker.prototype.sectionIsLoaded = function(sectionId) {
        if (!sectionId || !this.mainSections.hasOwnProperty(sectionId)) {
            return false;
        }
        return this.mainSections[sectionId].loaded;
    };

    FieldsChecker.prototype.initSectionData = function() {
        var self = this, sections = self.getSections(), tnthAjax = this.__getDependency("tnthAjax");
        var initDataObj = {
            "topTerms": function() {
                tnthAjax.getTerms(self.userId, "", "", function() {
                    self.setSectionDataLoadedFlag("topTerms", true);
                });
            },
            "demographicsContainer": function() {
                tnthAjax.getDemo(self.userId, {useWorker:true}, function() {
                    self.setSectionDataLoadedFlag("demographicsContainer", true);
                });
            },
            "clinicalContainer": function() {
                tnthAjax.getTreatment(self.userId, {useWorker:true}, function() {
                    tnthAjax.getClinical(self.userId, {async:false}, function() {
                        self.setSectionDataLoadedFlag("clinicalContainer", true);
                    });
                });
            },
            "orgsContainer": function() {
                tnthAjax.getDemo(self.userId, {useWorker:true}, function() {
                    self.setSectionDataLoadedFlag("orgsContainer", true);
                });
            }
        };
        for (var section in sections) {
            if (!initDataObj.hasOwnProperty(section)) {
                continue;
            }
            if (self.sectionCompleted(section)) {
                continue;
            }
            initDataObj[section](); //will initialize data for the first/current incomplete section
            break;
        }
    };

    FieldsChecker.prototype.getSections = function() {
        return this.mainSections;
    };

    FieldsChecker.prototype.initSections = function() {
        this.mainSections = {};
        var self = this;
        $("#mainDiv .section-container").each(function() {
            var sectionId = $(this).attr("id");
            if (!sectionId) {
                return true;
            }
            var sectionObj = self.mainSections[sectionId] = {};
            sectionObj.config =  $(this).attr("data-config");
            sectionObj.display = $(this).attr("data-display");
        });
    };

    FieldsChecker.prototype.postDemoData = function(targetField) {
        var demoArray = {}, tnthAjax = this.__getDependency("tnthAjax");
        demoArray.resourceType = "Patient";
        var fname = $("input[name=firstname]").val(), lname = $("input[name=lastname]").val();
        demoArray.name = {"given": $.trim(fname), "family": $.trim(lname)};
        var y = $("#year").val(), m = $("#month").val(), d = $("#date").val();
        if (y && m && d) {
            demoArray.birthDate = y + "-" + m + "-" + d;
        }
        var sectionId = this.getSectionContainerId(targetField);
        tnthAjax.putDemo(this.userId, demoArray, $("#"+sectionId));
        this.handlePostEvent(sectionId);
    };

    FieldsChecker.prototype.setUserRoles = function(callback) {
        var self = this, tnthAjax = self.__getDependency("tnthAjax");
        callback = callback || function() {};
        tnthAjax.getRoles(this.userId, function(data) {
            if (data.roles) {
                self.userRoles = data.roles.map(function(item) {
                    return item.name;
                });
            } else {
                tnthAjax.removeCachedRoles();
            }
            self.roleRequired = self.userRoles.indexOf("patient") !== -1 || self.userRoles.indexOf("staff") !== -1 || self.userRoles.indexOf("staff_admin") !== -1;
            callback();
        });
    };

    FieldsChecker.prototype.initConfig = function(callback) {
        var self = this, tnthAjax = self.__getDependency("tnthAjax");
        tnthAjax.getStillNeededCoreData(self.userId, true, function(data) {
            self.setConfig(data, callback);
        });
    };

    FieldsChecker.prototype.inConfig = function(configMatch, dataArray) {
        if (!hasValue(configMatch)) {
            return false;
        }
        dataArray = dataArray || this.CONFIG_REQUIRED_CORE_DATA;
        if (!dataArray || dataArray.length === 0) { return false; }
        var found = false;
        var ma = configMatch.split(",");
        ma.forEach(function(item) {
            if (found) { return true; } /* IMPORTANT, immediately return true. without checking this item, this is in the context of the loop, the sequence matters here, loop still continues*/
            found = dataArray.indexOf(item) !== -1;
        });
        return found;
    };

    FieldsChecker.prototype.getConfig = function() {
        return this.CONFIG_REQUIRED_CORE_DATA;
    };

    FieldsChecker.prototype.setConfig = function(data, callback) {
        callback = callback || function() {};
        var tnthAjax = this.__getDependency("tnthAjax");
        if (data && data.still_needed) {
            var fields = (data.still_needed).map(function(item) {
                return item.field;
            });
            this.CONFIG_REQUIRED_CORE_DATA = fields;
            this.handleAcceptOnNext(data);
        }
        if (!this.CONFIG_REQUIRED_CORE_DATA) { //get default required core data
            var self = this;
            tnthAjax.getConfigurationByKey("REQUIRED_CORE_DATA", {
                sync: true
            }, function(data) {
                if (!data.error) {
                    self.CONFIG_REQUIRED_CORE_DATA = data.REQUIRED_CORE_DATA;
                }
            });
        }
        this.setUserRoles(callback);
    };

    FieldsChecker.prototype.handleAcceptOnNext = function(data) {
        if (!data || !data.still_needed) {
            return false;
        }
        var ACCEPT_ON_NEXT = "ACCEPT_ON_NEXT"; /* example data format:[{"field": "name"}, {"field": "website_terms_of_use", "collection_method": "ACCEPT_ON_NEXT"}]*/
        var acceptOnNextCheckboxes = [];
        var self = this;
        (data.still_needed).forEach(function(item) {
            var matchedTermsCheckbox = $("#termsCheckbox [data-type='terms'][data-core-data-type='" + $.trim(item.field) + "']");
            if (matchedTermsCheckbox.length === 0) {
                return;
            }
            matchedTermsCheckbox.attr({"data-required": "true","data-collection-method": item.collection_method});
            var parentNode = matchedTermsCheckbox.closest("label.terms-label");
            if (parentNode.length === 0) {
                return;
            }
            parentNode.show().removeClass("tnth-hide");
            if (String(item.collection_method).toUpperCase() === ACCEPT_ON_NEXT) {
                parentNode.find("i").removeClass("fa-square-o").addClass("fa-check-square-o").addClass("edit-view");
                acceptOnNextCheckboxes.push(parentNode);
            }
        });
        if (acceptOnNextCheckboxes.length === 0) {
            return false;
        }
        this.ACCEPT_ON_NEXT = true; //set flag
        //require for accept on next collection method
        $("#termsCheckbox, #topTerms .terms-of-use-intro").addClass("tnth-hide");
        $("#termsText").addClass("agreed");
        $("#termsCheckbox_default").removeClass("tnth-hide");
        $("#aboutForm .reg-complete-container").addClass("inactive"); //hiding thank you and continue button for accept on next collection method
        $("#next").addClass("accept-on-next").on("click", function() {
            acceptOnNextCheckboxes.forEach(function(ckBox) {
                ckBox.trigger("click");
            });
        });
        //show next button for data collection method of accept on next - such as organizations like Music
        setTimeout(function() {
            $("#aboutForm").removeClass("tnth-hide");
            $("#next").removeAttr("disabled").addClass("open");
        }, 1000);
    };

    FieldsChecker.prototype.getTotalSections = function() {
        return Object.keys(this.mainSections).length;
    };

    FieldsChecker.prototype.constructProgressBar = function() {
        //don't construct progress bar when terms present
        if ($("#topTerms").length > 0 && !this.sectionCompleted("topTerms")) {
            return false;
        }
        var self = this;
        var totalSections = self.getTotalSections();
        if (totalSections <= 1) {
            $("#progressWrapper").remove();
            return;
        }
        var availableSections = 0;
        for (var section in self.mainSections) {
            var sectionConfigs = self.getSectionConfigs(section);
            var active = (section === "topTerms" && !self.inConfig(sectionConfigs)) || (self.roleRequired && !self.inConfig(sectionConfigs));
            $("#progressbar").append("<li sectionId='" + section + "'  " + (active ? " class='active'" : "") + ">" + self.mainSections[section].display + "</li>");
            availableSections++;
        }
        if (availableSections === 0) {
            return;
        }
        var w = (1 / availableSections) * 100;
        $("#progressbar li").each(function() {
            $(this).css("width", w + "%");
        });
        if (availableSections > 1) {
            $("#progressWrapper").show();
        }
    };

    FieldsChecker.prototype.setProgressBar = function(sectionId) {
        if (!hasValue(sectionId)) {
            return;
        }
        if (this.sectionCompleted(sectionId)) {
            $("#progressbar li[sectionId='" + sectionId + "']").addClass("active");
        } else {
            $("#progressbar li[sectionId='" + sectionId + "']").removeClass("active");
        }
    };

    FieldsChecker.prototype.getSectionConfigs = function(sectionId) {
        if (!sectionId || !this.mainSections[sectionId]) {
            return false;
        }
        return this.mainSections[sectionId].config;
    };

    FieldsChecker.prototype.sectionCompleted = function(sectionId, configArray) {
        if (!sectionId || !this.mainSections[sectionId]) {
            return false;
        }
        var sectionConfigs = this.getSectionConfigs(sectionId);
        return !this.inConfig(sectionConfigs, configArray || this.CONFIG_REQUIRED_CORE_DATA);
    };

    FieldsChecker.prototype.scrollTo = function(element) {
        if (!element) {
            return;
        }
        setTimeout(function() {
            $("html, body").stop().animate({
                scrollTop: $(element).offset().top
            }, 1500);
        }(), 800);
    };

    FieldsChecker.prototype.continueToFinish = function(sectionId) {
        this.hideSectionSavingLoader(sectionId);
        if ($("div.reg-complete-container").hasClass("inactive") || this.ACCEPT_ON_NEXT) { //button not needed continue to next directly
            window.location.reload();
            return false;
        }
        $("#progressWrapper").hide();
        $("#iqRefresh").addClass("tnth-hide");
        $("#next").attr("disabled", true).removeClass("open");
        $("#buttonsContainer").addClass("continue");
        $("#aboutForm").removeClass("tnth-hide");
        $("div.reg-complete-container").fadeIn();
        this.scrollTo($("div.reg-complete-container"));
        $("#iqErrorMessage").text("");
        $("#updateProfile").removeAttr("disabled").addClass("open");
    };

    FieldsChecker.prototype.stopContinue = function(sectionId) {
        this.hideSectionSavingLoader(sectionId);
        $("#buttonsContainer").removeClass("continue");
        $("#updateProfile").attr("disabled", true).removeClass("open");
        $("#buttonsContainer .loading-message-indicator").hide();
        $("div.reg-complete-container").fadeOut();
        $("#next").attr("disabled", true).addClass("open");
        this.setProgressBar(sectionId);
    };

    FieldsChecker.prototype.continueToNext = function(sectionId) {
        this.setProgressBar(sectionId);
        this.hideSectionSavingLoader(sectionId);
        $("#aboutForm").removeClass("tnth-hide");
        $("#iqRefresh").addClass("tnth-hide");
        $("#buttonsContainer").removeClass("continue");
        $("div.reg-complete-container").fadeOut();
        $("#next").removeAttr("disabled").addClass("open");
        this.scrollTo($("#next"));
        $("#updateProfile").attr("disabled", true).removeClass("open");
    };


    FieldsChecker.prototype.getNext = function() {
        var found = false,
            self = this;
        for (var section in self.mainSections) {
            if (!found && !self.sectionCompleted(section)) {
                self.handleIncomplete(section);
                $("#" + section).fadeIn(500).addClass("open");
                self.stopContinue(section);
                found = true;
            }
        }
        if (!found) {
            self.continueToFinish();
        }
    };

    FieldsChecker.prototype.handleIncomplete = function(section) {
        var preselectClinic = this.preselectClinic, self = this, i18next = this.__getDependency("i18next");
        var handleIncompleteFuncObj = {
            "topTerms": function() {
                $("#aboutForm").addClass("full-size");
                $("#topTerms").removeClass("hide-terms").show();
                if (!window.performance || self.ACCEPT_ON_NEXT) {
                    return false;
                }
                if (performance.navigation.type === 1) {
                    //page has been reloaded;
                    var agreedCheckboxes = $("#topTerms [data-required][data-agree='false']");
                    if (agreedCheckboxes.length > 1) {
                        $("#termsReminderCheckboxText").text(i18next.t("You must agree to the terms and conditions by checking the provided checkboxes."));
                    }
                    if (agreedCheckboxes.length === 0) {
                        $("#termsText").addClass("agreed");
                    }
                    $("#termsReminderModal").modal("show");
                }
                setTimeout(function() {disableHeaderFooterLinks();}, 1000);
            },
            "orgsContainer": function() {
                if (hasValue(preselectClinic)) {
                    self.handlePreSelectedClinic();
                    var __modal = self.getConsentModal();
                    if (__modal) {
                        __modal.modal("show");
                    }
                }
                $("#orgsContainer").fadeIn(500).addClass("open");
            }
        };
        if (!this.mainSections[section]) {
            return false;
        }
        if (handleIncompleteFuncObj.hasOwnProperty(section)) {
            handleIncompleteFuncObj[section]();
        }
    };

    FieldsChecker.prototype.currentSectionLoaded = function() {
        var self = this, isLoaded = true;
        //check all
        for (var section in self.mainSections) {
            if (!self.mainSections.hasOwnProperty(section) || self.sectionCompleted(section)) {
                continue;
            }
            if (!isLoaded) {
                break;
            }
            if (!self.sectionCompleted(section)) {
                isLoaded = self.sectionIsLoaded(section);
                break;
            }
        }
        return isLoaded;
    };

    FieldsChecker.prototype.getFieldEventType = function(field) {
        var triggerEvent = $(field).attr("data-trigger-event");
        if (!hasValue(triggerEvent)) {
            triggerEvent = ($(field).attr("type") === "text" ? "blur" : "click");
        }
        if ($(field).get(0).nodeName.toLowerCase() === "select") {
            triggerEvent = "change";
        }
        return triggerEvent;
    };

    FieldsChecker.prototype.initFields = function() {
        var self = this;
        var events = {
            "topTerms": function() {
                self.termsCheckboxEvent();
            },
            "demographicsContainer": function() {
                self.nameGroupEvent();
                self.bdGroupEvent();
                self.rolesGroupEvent();

            },
            "clinicalContainer": function() { self.patientQEvent(); },
            "orgsContainer": function() { self.clinicsEvent(); }
        };
        for (var sectionId in this.mainSections) {
            if (self.sectionCompleted(sectionId)) {
                continue;
            }
            if (events[sectionId]) {
                events[sectionId]();
            }
        }
    };

    FieldsChecker.prototype.onFieldsDidInit = function() {
        var self = this;
        /****** prep work after initializing incomplete fields -set visuals e.g. top terms ************************/
        self.constructProgressBar();

        $("#updateProfile").on("click", function() {
            $(this).hide();
            $("#next").hide();
            $(".loading-message-indicator").show();
            $("#queriesForm").submit();
        });

        $("#iqRefresh").on("click", function() {
            window.location.reload();
        });
        /*** event for the next button ***/
        $("#next").on("click", function() {
            $(this).hide();
            $("#buttonsContainer .loading-message-indicator").show();
            if (self.ACCEPT_ON_NEXT) {
                self.handlePostEvent("topTerms");
            } else {
                setTimeout(function() {
                    window.location.reload();
                }, 150);
            }
        });
        /*** event for the arrow in the header**/
        $("div.heading").on("click", function() {
            $("html, body").animate({
                scrollTop: $(this).next("div.content-body").children().first().offset().top
            }, 1000);
        });
        $(window).bind("scroll mousedown mousewheel keyup", function() {
            if ($("html, body").is(":animated")) {
                $("html, body").stop(true, true);
            }
        });
        //if term of use form not present - need to show the form
        if ($("#topTerms").length === 0) {
            $("#aboutForm").fadeIn();
            self.getNext();
        } else {
            if (!self.sectionCompleted("topTerms")) {
                self.handleIncomplete("topTerms");
            } else {
                $("#aboutForm").removeClass("full-size");
                self.getNext();
                $("#aboutForm").fadeIn();
            }
        }
        setTimeout(function() {
            $("#iqFooterWrapper").show();
        }, 500);
    };

    FieldsChecker.prototype.getSectionContainerId = function(field) {
        return $(field).closest(".section-container").attr("id");
    };

    FieldsChecker.prototype.handleRefreshElement = function(sectionId) {
        if (!sectionId || $("#iqRefresh").length) {
            return;
        }
        var i18next = this.__getDependency("i18next");
        var contentHTML = "<div id='iqRefresh' class='error-message tnth-hide'><i class='fa fa-refresh refresh-icon' aria-hidden='true'></i><span>{text}</span></div>".replace("{text}", i18next.t("Try Again"));
        var contentElement = $("#"+sectionId).find(".content-body");
        if (contentElement.length) {
            contentElement.append(contentHTML);
        } else {
            $("#"+sectionId).append(contentHTML);
        }
        $("#iqRefresh").on("click", function() {
            window.location.reload();
        });
    };

    FieldsChecker.prototype.isSavingInProgress = function(sectionId) {
        if (!sectionId) {
            return false;
        }
        return ($("#"+sectionId).find(".loading").length > 0);
    };

    FieldsChecker.prototype.sectionHasError = function(sectionId) {
        if (!sectionId) {
            return false;
        }
        var hasError = false;
        $("#" + sectionId + " .error-message").each(function() { //check for errors
            if (!hasError) { //short circuit the loop through elements
                hasError = hasValue($(this).text());
            }

        });
        return hasError;
    };

    FieldsChecker.prototype.showSectionSavingLoader = function(sectionId) {
        if (!sectionId) {
            return false;
        }
        $("#"+sectionId).find(".data-saving-indicator").removeClass("tnth-hide");
    };

    FieldsChecker.prototype.hideSectionSavingLoader = function(sectionId) {
        if (!sectionId) {
            return false;
        }
        $("#"+sectionId).find(".data-saving-indicator").addClass("tnth-hide");
    };

    FieldsChecker.prototype.handleSectionError = function(sectionId) {
        this.stopContinue(sectionId);
        this.handleRefreshElement(sectionId);
        $("#iqRefresh").removeClass("tnth-hide");
    };

    FieldsChecker.prototype.handlePostEvent = function(sectionId) {
        var self = this, elapsedSaveTime = 0;
        window.startDataSavingTime = new Date();
        window.endDataSavingTime = new Date();
        this.showSectionSavingLoader(sectionId);
        clearInterval(window.dataSavingIntervalId);
        window.dataSavingIntervalId = setInterval(function() {
            window.endDataSavingTime = new Date();
            elapsedSaveTime = window.endDataSavingTime - window.startDataSavingTime;
            elapsedSaveTime  /= 1000;
            var loadingInProgress = self.isSavingInProgress(sectionId);
            if (elapsedSaveTime < 0.5 || (loadingInProgress && elapsedSaveTime < 10)) {
                return false;
            }
            window.startDataSavingTime = 0;
            window.endDataSavingTime = 0 ;
            clearInterval(window.dataSavingIntervalId);

            var hasError = self.sectionHasError(sectionId);
            if (hasError) {
                self.handleSectionError(sectionId);
                return false;
            }
            var tnthAjax = self.__getDependency("tnthAjax");
            tnthAjax.getStillNeededCoreData(self.userId, false, function(data) {
                if (!data || data.error) {
                    self.stopContinue(sectionId);
                    return false;
                }
                if (!data.still_needed || !data.still_needed.length) {//finished all sections
                    self.continueToFinish(sectionId);
                    return true;
                }
                self.setConfig(data, function(){
                    setTimeout(function() {
                        self.hideSectionSavingLoader(sectionId);
                    }, 50);
                    if (self.sectionCompleted(sectionId)) {
                        self.continueToNext(sectionId);
                    }
                });
            });
        }, 150);
    };

    FieldsChecker.prototype.updateTerms = function(data) {
        function typeInTous(type, status) {
            var found = false, isActive = String(status) === "active";
            (data.tous).forEach(function(item) {
                if (!found &&
                    ($.trim(item.type) === $.trim(type)) &&
                    (String($.trim(item.active)) === String(isActive))) {
                    found = true;
                }
            });
            return found;
        }
        if (data.tous) {
            $("#termsCheckbox label.terms-label").each(function() {
                var item_found = 0;
                var self = $(this);
                self.find("[data-type='terms']").each(function() {
                    var type = $(this).attr("data-tou-type");
                    if (typeInTous(type, "active")) {
                        item_found++;
                        $("#termsCheckbox [data-tou-type='" + type + "']").attr("data-agree", "true"); //set the data-agree attribute for the corresponding consent item

                    }
                    if (typeInTous(type, "inactive")) {
                        self.attr("data-reconsent", "true");
                        self.closest("#termsCheckbox").attr("data-reconsent", "true");
                    }
                });
                if (item_found > 0) {
                    if (self.find("[data-agree='false']").length === 0) { // make sure that all items are agreed upon before checking the box
                        self.find("i").removeClass("fa-square-o").addClass("fa-check-square-o").addClass("edit-view");
                        var vs = self.find(".display-view");
                        if (vs.length > 0) {
                            self.show();
                            vs.show();
                            (self.find(".edit-view")).each(function() {
                                $(this).hide();
                            });
                        } else {
                            self.hide();
                            return true;
                        }
                    }
                    self.show().removeClass("tnth-hide");
                }
            });
        }
    };

    FieldsChecker.prototype.termsCheckboxEvent = function() {
        var __self = this;
        var userId = __self.userId, tnthAjax = this.__getDependency("tnthAjax"), orgTool = this.getOrgTool();
        var termsEvent = function() {
            if ($(this).attr("data-agree") === "false") {
                var types = $(this).attr("data-tou-type");
                if (hasValue(types)) {
                    var arrTypes = types.split(","), dataUrl = $(this).attr("data-url");
                    arrTypes.forEach(function(type) {
                        if ($("#termsCheckbox [data-agree='true'][data-tou-type='" + type + "']").length > 0) { //if already agreed, don't post again
                            return true;
                        }
                        var theTerms = {};
                        theTerms["agreement_url"] = hasValue(dataUrl) ? dataUrl : $("#termsURL").data().url;
                        theTerms["type"] = type;
                        var org = $("#userOrgs input[name='organization']:checked"),
                            userOrgId = org.val();
                        /*** if UI for orgs is not present, need to get the user org from backend ***/
                        if (!userOrgId) {
                            $.ajax({
                                type: "GET",
                                url: "/api/demographics/" + userId,
                                async: false
                            }).done(function(data) {
                                if (data && data.careProvider) {
                                    (data.careProvider).forEach(function(item) {
                                        if (!userOrgId) {
                                            userOrgId = item.reference.split("/").pop();
                                            return true;
                                        }
                                    });
                                }
                            }).fail(function() {});
                        }
                        if (hasValue(userOrgId) && parseInt(userOrgId) !== 0 && !isNaN(parseInt(userOrgId))) {
                            var topOrg = orgTool.getTopLevelParentOrg(userOrgId);
                            theTerms["organization_id"] = topOrg || userOrgId;
                        }
                        if (!theTerms["organization_id"] || !theTerms["agreement_url"]) { //this will display error to user if information is missing
                            $("#topTerms .post-tou-error").html(i18next.t("Missing information for organization and consent agreement.  Unable to complete request."));
                            return;
                        }
                        tnthAjax.postTerms(theTerms, $("#topTerms")); // Post terms agreement via API
                    });
                }
                // Update UI
                if (this.nodeName.toLowerCase() === "label") {
                    $(this).find("i").removeClass("fa-square-o").addClass("fa-check-square-o");
                } else {
                    $(this).closest("label").find("i").removeClass("fa-square-o").addClass("fa-check-square-o");
                }
                //adding css rule here so the checkbox won't be hidden on click
                $(this).attr("current", "true");
                $(this).attr("data-agree", "true");

                var coreTypes = [], parentCoreType = $(this).attr("data-core-data-type");
                if (hasValue(parentCoreType)) {
                    coreTypes.push(parentCoreType);
                }
                $(this).closest("label").find("[data-core-data-type]").each(function() {
                    var coreDataType = $(this).attr("data-core-data-type");
                    if($.inArray(coreDataType, coreTypes) === -1) {
                        coreTypes.push(coreDataType);
                    }
                });
                if (coreTypes.length > 0) { //need to delete notification for each corresponding coredata terms type once user has agreed
                    coreTypes.forEach(function(type) {
                        var notificationEntry = $("#notificationBanner [data-name='" + type + "_update']");
                        if (notificationEntry.length > 0) {
                            Global.deleteNotification($("#notificationUserId").val(), notificationEntry.attr("data-id")); /*global Global */
                        }
                    });
                }
                __self.handlePostEvent(__self.getSectionContainerId($(this)));
            }
        };
        $("#topTerms label.terms-label").each(function() { //account for the fact that some terms items are hidden as child elements to a label
            $(this).on("click", function() {
                if ($(this).attr("data-required")) {
                    termsEvent.apply(this);
                } else {
                    $(this).find("[data-required]").each(function() {
                        termsEvent.apply(this);
                    });
                }
            });
        });

        $("#topTerms [data-type='terms'][data-required='true']").each(function() {
            $(this).on(__self.getFieldEventType($(this)), termsEvent);
        });

        $("#topTerms .required-link").each(function() {
            $(this).on("click", function(e) {
                e.stopPropagation();
            });
        });
    };

    FieldsChecker.prototype.nameGroupEvent = function() {
        var self = this;
        $("#firstname, #lastname").each(function() {
            $(this).on(self.getFieldEventType($(this)), function() {
                if ($(this).val() !== "") {
                    self.postDemoData($(this));
                }
            });
        });
    };

    FieldsChecker.prototype.bdGroupEvent = function() {
        var self = this, tnthDates = this.__getDependency("tnthDates");
        $("#month, #date, #year").each(function() {
            $(this).on(self.getFieldEventType($(this)), function() {
                var d = $("#date"), m = $("#month"), y = $("#year");
                var isValid = tnthDates.validateDateInputFields(m, d, y, "errorbirthday");
                if (!isValid) {
                    return false;
                }
                $("#birthday").val(y.val() + "-" + m.val() + "-" + d.val());
                $("#errorbirthday").text("").hide();
                self.postDemoData($(this));
            });
        });
        __convertToNumericField($("#date, #year"));
    };

    FieldsChecker.prototype.rolesGroupEvent = function() {
        var self = this, tnthAjax = this.__getDependency("tnthAjax");
        $("input[name='user_type']").on("click", function() {
            var roles = [], theVal = $(this).val();
            roles.push({name: theVal});
            tnthAjax.putRoles(self.userId,{"roles": roles}, $("#rolesGroup"));
            self.handlePostEvent(self.getSectionContainerId($(this)));
        });
    };

    FieldsChecker.prototype.patientQEvent = function() {
        var self = this;
        $("#patientQ [data-topic] input[type='radio']").on("click", function() {
            var thisItem = $(this);
            var toCall = thisItem.attr("name") || thisItem.attr("data-name");
            var toSend = (toCall === "biopsy" ? ($("#patientQ input[name='biopsy']:checked").val()) : thisItem.val());
            if (toSend === "true" || toCall === "pca_localized") {
                if (toCall === "biopsy" && !$("#biopsyDate").val()) {
                    return true;
                }
                thisItem.parents(".pat-q").next().fadeIn(150);
                var nextRadio = thisItem.closest(".pat-q").next(".pat-q");
                var nextItem = nextRadio.length > 0 ? nextRadio : thisItem.parents(".pat-q").next();
                if (nextItem.length > 0) {
                    var checkedRadio = nextItem.find("input[type='radio']:checked");
                    if (!(checkedRadio.length > 0)) {
                        $("html, body").animate({scrollTop: nextItem.offset().top}, 1000);
                    }
                }
            } else {
                thisItem.parents(".pat-q").nextAll().fadeOut(150);
            }
            self.handlePostEvent(self.getSectionContainerId($(this)));
        });
    };
    FieldsChecker.prototype.getConsentModal = function(parentOrg) {
        var orgTool = this.getOrgTool();
        parentOrg = parentOrg || orgTool.getElementParentOrg(orgTool.getSelectedOrg());
        if (parentOrg) {
            var __modal = $("#" + parentOrg + "_consentModal");
            if (__modal.length > 0) {
                return __modal;
            } else {
                var __defaultModal = $("#" + parentOrg + "_defaultConsentModal");
                if (__defaultModal.length > 0) {
                    return __defaultModal;
                }
            }
            return false;
        } else {
            return false;
        }
    };
    FieldsChecker.prototype.handlePreSelectedClinic = function() {
        var preselectClinic = $("#preselectClinic").val(), orgTool = this.getOrgTool();
        if (preselectClinic) {
            var ob = $("#userOrgs input[value='" + preselectClinic + "']");
            if (ob.length > 0) {
                ob.prop("checked", true);
                var parentOrg = orgTool.getElementParentOrg(orgTool.getSelectedOrg());
                var __modal = this.getConsentModal(parentOrg);
                if (__modal) {
                    ob.attr("data-require-validate", "true");
                }
                var stateContainer = ob.closest(".state-container");
                var st = stateContainer.attr("state");
                if (stateContainer.length > 0 && st) {
                    $("#stateSelector").find("option[value='" + st + "']").prop("selected", true).val(st);
                    stateContainer.show();
                }
            }
        }
    };

    FieldsChecker.prototype.clinicsEvent = function() {
        var self = this;
        $("#userOrgs input[name='organization']").not("[type='hidden']").on("click", function() {
            if ($(this).prop("checked")) {
                var parentOrg = $(this).attr("data-parent-id"), m = $("#consentContainer .modal, #defaultConsentContainer .modal");
                var requiringConsentViaModal = ($("#fillOrgs").attr("patient_view") && m.length > 0 && parseInt($(this).val()) !== 0);
                if (requiringConsentViaModal) { //do nothing
                    return true;
                }
                self.handlePostEvent(self.getSectionContainerId($(this)));

            }
        });
        $("#stateSelector").on("change", function() {
            if (!$(this).val()) {
                return;
            }
            self.scrollTo($("#clinics .state-selector-container.selector-show"));
        });
        /*** event for consent popups **/
        $("#consentContainer .modal, #defaultConsentContainer .modal").each(function() {
            $(this).on("hidden.bs.modal", function() {
                if ($(this).find("input[name='toConsent']:checked").length > 0) {
                    $("#userOrgs input[name='organization']").each(function() {
                        $(this).removeAttr("data-require-validate");
                    });
                    self.handlePostEvent(self.getSectionContainerId($(this)));
                }
            });
        });
    };
    window.FieldsChecker = FieldsChecker;

    $(document).ready(function() {
        /*
         * the flow here :
         * get still needed core data
         * populate all required fields
         * get incomplete fields thereafter
         * note: need to delay gathering incomplete fields to allow fields to be render
         */
        if ($("#aboutForm").length > 0 || $("#topTerms").length > 0) { /*global i18next, tnthAjax, OrgTool, tnthDates*/
            var fc = window.fc = new window.FieldsChecker({
                i18next: i18next,
                tnthAjax: tnthAjax,
                orgTool: new OrgTool(),
                tnthDates: tnthDates
            });
            fc.init(function() {
                fc.startTime = new Date();
                DELAY_LOADING = true; /*global DELAY_LOADING */
                clearInterval(fc.intervalId);
                fc.intervalId = setInterval(function() {
                    fc.endTime = new Date();
                    var elapsedTime = fc.endTime - fc.startTime;
                    elapsedTime /= 1000;
                    if (fc.currentSectionLoaded() || elapsedTime >= 5) {
                        setTimeout(function() {
                            fc.initFields();
                            fc.onFieldsDidInit();
                            DELAY_LOADING = false;
                            showMain(); /* global showMain */
                            hideLoader(true); /* global hideLoader */
                        }, 300);
                        fc.startTime = 0;
                        fc.endTime = 0;
                        clearInterval(fc.intervalId);
                    }
                }, 100);
            });
        }
    });
})();

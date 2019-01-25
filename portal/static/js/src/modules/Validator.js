import Utility from "./Utility.js";
import tnthDates from "./TnthDate.js";

var ValidatorObj = { /*global  $ i18next */
    "birthdayValidation": function() {
        var m = parseInt($("#month").val()), d = parseInt($("#date").val()), y = parseInt($("#year").val());
        return  tnthDates.validateDateInputFields(m, d, y, "errorbirthday");
    },
    "emailValidation": function($el) {
        var emailVal = $.trim($el.val());
        var update = function($el) {
            if ($el.attr("data-update-on-validated") === "true" && $el.attr("data-user-id")) {
                $el.trigger("postEventUpdate");
            }
        };
        if (emailVal === "") {
            if (!$el.attr("data-optional")) {
                return false;
            }
            update($el); //if email address is optional, update it as is
            return true;
        }
        var emailReg = /^(([^<>()[\]\\.,;:\s@\"]+(\.[^<>()[\]\\.,;:\s@\"]+)*)|(\".+\"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
        var addUserId = ""; // Add user_id to api call (used on patient_profile page so that staff can edit)
        if ($el.attr("data-user-id")) {
            addUserId = "&user_id=" + $el.attr("data-user-id");
        }
        if (emailReg.test(emailVal)) {  // If this is a valid address, then use unique_email to check whether it's already in use
            var url = "/api/unique_email?email=" + encodeURIComponent(emailVal) + addUserId;
            Utility.sendRequest(url, {max_attempts:1}, function(data) {
                if (data && data.constructor === String) {
                    data = JSON.parse(data);
                }
                if (data.error) { //note a failed request will be logged
                    $("#erroremail").html(i18next.t("Error occurred when verifying the uniqueness of email")).parents(".form-group").addClass("has-error");
                    return false; //stop proceeding to update email
                }
                if (data.unique) {
                    $("#erroremail").html("").parents(".form-group").removeClass("has-error");
                    update($el);
                    return true;
                }
                $("#erroremail").html(i18next.t("This e-mail address is already in use. Please enter a different address.")).parents(".form-group").addClass("has-error");
            });
        }
        return emailReg.test(emailVal);
    },
    htmltagsValidation: function($el) {
        var containHtmlTags = function(text) {
            if (!(text)) {return false;}
            return /[<>]/.test(text);
        };
        var invalid = containHtmlTags($el.val());
        if (invalid) {
            $("#error" + $el.attr("id")).html(i18next.t("Invalid characters in text."));
            return false;
        }
        $("#error" + $el.attr("id")).html("");
        return !invalid;
    },
    initValidator: function() {
        if (typeof $.fn.validator === "undefined") { return false; }
        const VALIDATION_EVENTS = "change";
        let self = this;
        /*
         * init validation event for fields with custom validation attribute
         */
        $("form.to-validate[data-toggle=validator] [data-birthday]").attr("novalidate", true).on(VALIDATION_EVENTS,function() {
            return self.birthdayValidation($(this));
        });
        $("form.to-validate[data-toggle=validator] [data-customemail]").attr("novalidate", true).on(VALIDATION_EVENTS, function() {
            return self.emailValidation($(this));
        });
        $("form.to-validate[data-toggle=validator] [data-htmltags]").attr("novalidate", true).on(VALIDATION_EVENTS, function() {
            return self.htmltagsValidation($(this));
        });
    }
};
export default ValidatorObj;
export var emailValidation = ValidatorObj.emailValidation;
export var htmltagsValidation = ValidatorObj.htmltagsValidation;
export var birthdayValidation = ValidatorObj.birthdayValidation;



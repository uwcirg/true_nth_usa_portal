(function() { /* global $ i18next */
    var RegisterObj = window.RegisterObj = function() {
        this.__passwordReg = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$/;
        this.init = function() {
            var self = this;
            $(document).ready(function(){
                console.log("get to init??")
                self.initVis();
                self.initPasswordPopover();
                self.initFieldEvents();
            });
        };
        this.initVis = function() {
            // Need to properly form attribute name
            $("[data-match_error]").each(function(){
                $(this).attr("data-match-error", $(this).attr("data-match_error"));
            });
            $("input[type='submit']").addClass("disabled");
        };
        this.checkValidity = function(submit) {
            var allowed = true;
            ["#email", "#password", "#retype_password"].forEach(function(fieldId) {
                if (!$(fieldId).val()) {
                    allowed = false;
                }
            });
            if (allowed) {
                allowed = !($(".form-group.has-error").length);
            }
            if (allowed) {
                $("input[type='submit']").removeClass("disabled");
            } else {
                $("input[type='submit']").addClass("disabled");
            }
            if (!submit) {
                return;
            }
            $("input[type='submit']").trigger("click");
        };
        this.initFieldEvents = function() {
            var self = this;
            $("input.input-field").each(function() {
                $(this).on("blur, change", function() {
                    setTimeout(function() { self.checkValidity(); }, 350);
                });
                $(this).on("keyup", function(e) {
                    e.preventDefault();
                    setTimeout(function() { self.checkValidity(e.keyCode === 13); } , 350);
                });
            });
            $("#retype_password").on("keyup change", function() {
                if (!$(this).val()) {
                    $("#errorretype_password").addClass("has-error").text(i18next.t("Please re-type your password."));
                } else {
                    $("#errorretype_password").text("").removeClass("has-error");
                    self.checkValidity();
                }
            });
            $("#email").on("change", function() {
                $("#erroremail").text("");
            });

        };
        this.setPopoverVis = function(condition, field) {
            if (condition) {
                field.removeClass("fail-text").addClass("success-text");
            } else {
                field.removeClass("success-text").addClass("fail-text");
            }
        };
        this.initPasswordPopover = function() {
            var self = this;
            $("#password").popover({"content": $("#passwordPopover .popover-content").html(), "placement": "top", "html": true, "template": $("#passwordPopover").html(), "container": ".password-wrapper", "trigger": "manual"}).click(function(e) {
                $(this).trigger("focus");
                e.stopPropagation();
            }).on("keyup", function() {
                var pwd = $(this).val(), pwdTest = self.__passwordReg.test(pwd);
                var l = $("#password").data("bs.popover").tip().find("#pwdHintList");
                if (pwdTest) {
                    $("#errorpassword").text("");
                    self.setPopoverVis(pwdTest, l.find("li"));
                    setTimeout(function() {
                        $("#password").popover("hide");
                    }, 500);
                    return;
                }
                if (!$(this).data("bs.popover").tip().hasClass("in")) {
                    $(this).popover("show");
                }
                if (!pwd) {
                    l.find("li").removeClass("success-text").removeClass("fail-text");
                    return;
                }
                self.setPopoverVis(/[a-z]/.test(pwd), l.find(".lowercase-letter"));
                self.setPopoverVis(/[A-Z]/.test(pwd), l.find(".uppercase-letter"));
                self.setPopoverVis(/\d/.test(pwd), l.find(".one-number"));
                self.setPopoverVis(pwd.length >= 8, l.find(".eight-characters"));
            }).on("blur", function() {
                $(this).popover("hide");
            }).on("focus", function() {
                var pwd = $(this).val();
                if (!self.__passwordReg.test(pwd)) {
                    if (!$(this).data("bs.popover").tip().hasClass("in")) {
                        $(this).popover("show");
                    }
                } else {
                    return true;
                }
            }).on("shown.bs.popover", function () {
                $(this).trigger("keyup");
            }).on("paste", function() {
                $(this).trigger("keyup");
            });
            $("html").click(function() {
                $("#password").popover("hide");
            });
        };
    };
    (new RegisterObj()).init();
})();

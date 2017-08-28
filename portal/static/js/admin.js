//a workaround for wrapper not finished loading before the content displays, the finish loading of wrapper hides the loader
DELAY_LOADING = true;

function AdminTool (userId) {
  this.requestsCounter = 0;
  this.userId = userId;
  this.userOrgs = [];
  this.ajaxRequests = [];
  this.ajaxAborted = false;
  this.arrData = {};
  this.patientsIdList = [];
  OrgTool.call(this);
};

/*
* extends OrgTool class
* see OT class definition in main.js should modularize it in the future so it can be instantiated/called safely
*
*/
AdminTool.prototype = Object.create(OrgTool.prototype);
AdminTool.prototype.fadeLoader = function() {
  DELAY_LOADING = false;
  setTimeout(function() { $("#loadingIndicator").fadeOut(); }, 1000);
};
AdminTool.prototype.setLoadingMessageVis = function(vis) {
  switch(vis) {
    case "hide":
      $("#adminTable .field-loading-indicator").fadeOut();
      break;
    case "show":
      $("#adminTable .field-loading-indicator").fadeIn();
      break;
  };
};
AdminTool.prototype.setStatusLoadingVis = function(vis) {
  switch(vis) {
    case "hide":
      $("#adminTable th.status-field .loading-message-indicator").fadeOut();
      $("#adminTable .bootstrap-table-filter-control-status").css("opacity", 1);
      break;
    case "show":
      $("#adminTable th.status-field .loading-message-indicator").fadeIn();
      break;
  };
};
AdminTool.prototype.getPatientsIdList = function() {
  var self = this;
  if (self.patientsIdList.length == 0) {
    var all = $("#adminTable").bootstrapTable("getData");
    if (all) {
      all.forEach(function(o) {
        self.patientsIdList.push(o.id);
      });
    };
  };
  return self.patientsIdList;
};
/*
 * currently not being used - client side retrieval of assessment status
 */
AdminTool.prototype.getData = function(requests, callback) {
    var self = this;
    if (self.ajaxAborted) {
        return false;
    };
    if (!requests || requests.length == 0) {
        return false;
    };
    var userString = requests.shift();
    if (!hasValue(userString)) {
        return false;
    };
    /*
     *  load the data sequentially
     *  Note, NO concurrent ajax calls here,
     *  one request will wait after the previous one has finished
     */
    var ajaxRequest = $.ajax ({
                              type: "GET",
                              url: '/api/consent-assessment-status',
                              contentType: "application/json; charset=utf-8",
                              data: userString,
                              cache: false,
                              timeout: 5000,
                              beforeSend: function() {
                                self.setStatusLoadingVis("show");
                                /*
                                 * disable export functionality while status is being populated
                                 */
                                $("div.export button").attr("disabled", true);
                              },
                              dataType: 'json'
                          }).done(function(data) {
                                if (data && data.status) {
                                  data.status.forEach(function(status) {
                                      var c = status.consents;
                                      var a = "", s = "", prevItem = {};
                                      if (c) {
                                      c.forEach(function(item) {
                                          if (!item.consent.deleted && (!prevItem.consent_signed || (prevItem.assessment_status != item.assessment_status)
                                              || (String(prevItem.consent_signed).substring(0, 10) != String(item.consent.signed).substring(0, 10)))) {
                                              if (!(/null/.test(item.consent.agreement_url))) {
                                                var cl = "";
                                                var sd = tnthDates.formatDateString(item.consent.signed);
                                                var status = item.assessment_status;
                                                if (!item.consent.send_reminders) status = "withdrawn";
                                                switch(String(status).toLowerCase()) {
                                                    case "completed":
                                                      cl = "text-success";
                                                      break;
                                                    case "withdrawn":
                                                      cl = "text-muted";
                                                      break;
                                                    case "due":
                                                      cl = "text-warning";
                                                      break;
                                                    case "overdue":
                                                      cl = "text-danger";
                                                      break;
                                                };
                                                a += (a != "" ? "<br/>" : "") + "<span class='" + cl  + " small-text' style='text-transform: capitalize'>" + status + "</span>";
                                                s += (s != "" ? "<br/>" : "") + sd;
                                                prevItem.assessment_status = item.assessment_status;
                                                prevItem.consent_signed = item.consent.signed;
                                              };
                                            };
                                        });
                                    };
                                    if (hasValue(status.user_id)) {
                                      /*
                                       * NOTE, need to get the row data here
                                       * data for all the fields are required for the method, updateByUniqueId
                                       */
                                      var rowData = $("#adminTable").bootstrapTable('getRowByUniqueId', status.user_id);
                                      rowData = rowData || {};
                                      /* update row data with updated assessment status */
                                      rowData["status"] = a;
                                      /* persist data here, help with debugging */
                                      self.arrData[status.user_id] = { id: status.user_id, row: rowData};
                                      $("#adminTable").bootstrapTable('updateByUniqueId', self.arrData[status.user_id]);

                                    };
                              });
                            };
                            if (requests.length > 0) {
                              self.getData(requests, callback);
                            }
                            else {
                              if (callback) setTimeout(function() { callback.call(self);}, 300);
                              self.setStatusLoadingVis("hide");
                              $("div.export button").attr("disabled", false);
                            };
                        }).fail(function(xhr) {
                            self.setStatusLoadingVis("hide");
                            $("div.export button").attr("disabled", false);
                            $("#admin-table-error-message").text("Server error occurred updating row data.  Server error code: " + xhr.status);
                        });
        self.ajaxRequests.push(ajaxRequest);
        return ajaxRequest;
};
AdminTool.prototype.updateData = function() {
  /* compile user IDs array from patients list ID */
  var arrUsers = this.getUserIdArray();
  var self = this;
  if (arrUsers.length > 0) {
     self.getData(arrUsers);
  };
};
AdminTool.prototype.abortRequests = function(callback, showLoader) {
    var self = this;
   //NEED TO ABORT THE AJAX REQUESTS OTHERWISE CLICK EVENT IS DELAYED DUE TO NETWORK TIE-UP
   if (self.ajaxRequests.length > 0) {
      self.ajaxAborted = true;
      self.ajaxRequests.forEach(function(request, index, array) {

          try {
            if (parseInt(request.readyState) != 4) {
                /*
                 * aborting the request here to quit immediately, instead of waiting for the
                 * maximum timeout specified
                 */
                request.timeout = 100;
                request.abort();
            }
          } catch(e) {
          };
          if (index == array.length - 1) {
            $("#admin-table-error-message").text("");
            if (callback) {
              setTimeout(function() { callback();}, 100);
              if (showLoader) loader(true)
            };
          };
      });
    } else {
      if (callback) setTimeout(function() { callback();}, 100);
    };

};
AdminTool.prototype.getUserIdArray = function(_userIds) {
  var us = "", ct = 0, arrUsers = [];
  if (!_userIds) {
     _userIds = this.getPatientsIdList();
  };
  var max_ct = Math.max(_userIds.length/10, 10);

  for (var index = 0; index < _userIds.length; index++, ct++) {
     us += (us != ""?"&":"") + "user_id=" + _userIds[index];
     if (index == (_userIds.length - 1)) {
       arrUsers.push(us);
     } else if (ct >= max_ct) {
        arrUsers.push(us);
        us = "";
        ct = 0;
     };
  };
  return arrUsers;
};
AdminTool.prototype.setUserOrgs = function() {
  var self = this;
  if (!hasValue(this.userId)) return false;
  $.ajax ({
          type: "GET",
          async: false,
          url: '/api/demographics/'+this.userId
  }).done(function(data) {
    if (data && data.careProvider) {
      $.each(data.careProvider,function(i,val){
          var orgID = val.reference.split("/").pop();
          self.userOrgs.push(orgID);
          if (orgID == "0") $("#createUserLink").attr("disabled", true);
      });
    if (self.userOrgs.length == 0) $("#createUserLink").attr("disabled", true);
    };
  }).fail(function() {

  });
};
AdminTool.prototype.getUserOrgs = function() {
  if (this.userOrgs.length == 0) this.setUserOrgs(this.userId);
  return this.userOrgs;
};
AdminTool.prototype.initOrgsList = function(request_org_list, context) {
    //set user orgs
    var self = this;
    self.setUserOrgs();

    //check if the location contains filtered orgs list
    var iterated = /org_list/.test(location.href);

    var noPatientData = $("#admin-table-body").find("tr.no-records-found").length > 0;

    $.ajax ({
        type: "GET",
        url: '/api/organization'
    }).done(function(data) {

        /*
         * building an orgs array object for reference later
         */
        self.populateOrgsList(data.entry);
        /*
         * populate orgs dropdown UI
         */
        self.populateUI();

        /*
         * filter orgs UI based on user's orgs
         */
        if (!noPatientData) {
            var hbOrgs = self.getHereBelowOrgs(self.getUserOrgs());
	          self.filterOrgs(hbOrgs);
        } else {
          $("div.fixed-table-toolbar").hide();
        };

        var ofields = $("#userOrgs input[name='organization']");
        if (ofields.length > 0) {
          /* attach orgs related events to UI components */
          ofields.each(function() {
            if ((self.getHereBelowOrgs(self.getUserOrgs())).length == 1 ||
                (iterated && request_org_list && request_org_list[$(this).val()])) {
                $(this).prop("checked", true);
            }
            $(this).on("click touchstart", function(e) {
                e.stopPropagation();
                AT.abortRequests();
                var orgsList = [];
                $("#userOrgs input[name='organization']").each(function() {
                   if ($(this).is(":checked")) orgsList.push($(this).val());
                });
               if (orgsList.length > 0) {
                  location.replace("/" + context + "?org_list=" + orgsList.join(","));
               } else location.replace("/" + context);
            });
          });

          $("#org-menu").append("<hr><div id='orglist-footer-container'><label><input type='checkbox' id='orglist-selectall-ckbox'>&nbsp;<span class='text-muted'>" + i18next.t("Select All") + "</span></label>&nbsp;&nbsp;&nbsp;<label><input type='checkbox' id='orglist-clearall-ckbox'>&nbsp;<span class='text-muted'>" + i18next.t("Clear All") + "</span></label>&nbsp;&nbsp;&nbsp;<label><input type='checkbox' id='orglist-close-ckbox'>&nbsp;<span class='text-muted'>" + i18next.t("Close") + "</span></label></div>");
          $("#orglist-selectall-ckbox").on("click touchstart", function(e) {
              e.stopPropagation();
              var orgsList = [];
              $("#userOrgs input[name='organization']").each(function() {
                  if ($(this).is(":visible")) {
                    $(this).prop("checked", true);
                    orgsList.push($(this).val());
                  };
              });
              $("#orglist-clearall-ckbox").prop("checked", false);
              if (orgsList.length > 0) location.replace("/" + context + "?org_list=" + orgsList.join(","));
          });
          $("#orglist-clearall-ckbox").on("click touchstart", function(e) {
              e.stopPropagation();
              $("#userOrgs input[name='organization']").each(function() {
                  $(this).prop("checked", false);
              });
          });
          $("#orglist-close-ckbox").on("click touchstart", function(e) {
              e.stopPropagation();
              $("#orglistSelector").trigger("click");
              return false;
          });
        };

    }).fail(function() {
        //console.log("Problem retrieving data from server.");
        $("#org-menu").append("<span class='indent text-danger'>" + i18next.t("Error occurred retrieving data from server.") + "</span>");
    });

    //orglist-dropdown
    $('#orglist-dropdown').on('click touchstart', function () {
        setTimeout('AT.__setOrgsMenuHeight(100); AT.__clearFilterButtons();', 10);
    });

    if (noPatientData) $("#patientListExportDataContainer").hide();

    /*
     * private functions used only within the context of the class
     */
    this.__setOrgsMenuHeight = function(padding) {
      if (!padding) padding = 100;
      var h = parseInt($("#fillOrgs").height());
      if (!isNaN(h) && h > 0) {
        $("#org-menu").height(h + padding);
        if ($("div.admin-table").height() < $("#org-menu").height()) {
            setTimeout('$("div.admin-table").height($("#org-menu").height() + ' + padding + ');', 0);
        };
      };
    };
    this.__clearFilterButtons = function() {
      $("#orglist-close-ckbox, #orglist-clearall-ckbox, #orglist-selectall-ckbox").prop("checked", false);
    };
};
AdminTool.prototype.getInstrumentList = function() {
  var iList;
  tnthAjax.getInstrumentsList(true, function(data) {
    if (data && !data.error) {
      iList = data;
    };
  });
  return iList ? iList : false;
};

AdminTool.prototype.handleDownloadModal = function() {

    var self = this;
     /*
      *populate instruments list based on user's parent org
      */
    $("#dataDownloadModal").on('shown.bs.modal', function () {
        var instrumentList = self.getInstrumentList();
        if (instrumentList) {
          var parentOrgList = AT.getUserTopLevelParentOrgs(AT.getUserOrgs());
          if (parentOrgList && parentOrgList.length > 0) {
             var instrumentItems = [];
             parentOrgList.forEach(function(o) {
                var il = instrumentList[o];
                if (il) {
                  il.forEach(function(n) {
                    instrumentItems.push(n);
                  });
                };
             });
             if (instrumentItems.length > 0) {
                $(".instrument-container").hide();
                instrumentItems.forEach(function(item) {
                  $("#" + item + "_container").show();
                });
             };
          };
        };
        $("#patientsInstrumentList").addClass("ready");
    });
    /*
     * attach on click event to submit button in the download modal
     */
    $(document).delegate("#patientsDownloadButton", "click", function(event){
      var instruments = "", dataType = "";
      $("input[name='instrument'").each(function() {
          if ($(this).is(":checked")) {
            instruments += (instruments != "" ? "&": "") + "instrument_id="+$(this).val();
          };
      });
      $("input[name='downloadType']").each(function() {
          if ($(this).is(":checked")) dataType = $(this).val();
      });
      if (instruments != "" && dataType != "") {
          //alert(instruments)
          $("#_downloadMessage").text("");
          $("#_downloadLink").attr("href", "/api/patient/assessment?" + instruments + "&format=" + dataType);
          $("#_downloadLink")[0].click();
      } else {
          message = (instruments == "" ? i18next.t("Please choose at least one instrument."): "");
          if (dataType == "") message += (message != "" ? "<br/>": "") + i18next.t("Please choose one download type.");
          $("#_downloadMessage").html(message);
      };
    });

    /*
     * attach event to each checkbox in the download instruments modal
     */
    $("input[name='instrument'], input[name='downloadType']").on("click", function() {
        if ($(this).is(":checked")) $("#_downloadMessage").text("");
    });
}




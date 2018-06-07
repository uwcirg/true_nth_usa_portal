(function() {
    var psaApp = window.psaApp = new Vue({ /*global Vue*/
        el: "#mainPsaApp",
        components: {
        },
        errorCaptured: function(Error, Component, info) {
            console.error("Error: ", Error, " Component: ", Component, " Message: ", info);
            return false;
        },
        errorHandler: function(err, vm) {
            this.dataError = true;
            var errorElement = document.getElementById("psaTrackerErrorMessageContainer");
            if(errorElement) {
                errorElement.innerHTML = "Error occurred initializing PSA Tracker Vue instance.";
            }
            console.warn("PSA Tracker Vue instance threw an error: ", vm, this);
            console.error("Error thrown: ", err);
        },
        created: function() {
            VueErrorHandling(); /*global VueErrorHandling */
        },
        data: {
            userId: "",
            userIdKey: "psaTracker_currentUser",
            clinicalCode: "666",
            clinicalDisplay: "psa",
            clinicalSystem: "http://us.truenth.org/clinical-codes",
            loading: false,
            addErrorMessage: "",
            noResultMessage: this.i18next.t("No PSA results to display"),
            newItem: {
                id: "",
                result: "",
                date: "",
                edit: false
            },
            headers: [
                this.i18next.t("Date"),
                this.i18next.t("PSA (ng/ml)")
            ],
            items: [],
            history: {
                items: [],
                label: this.i18next.t("History")
            },
            originals: [],
            resultRange: ["<= 4", ">= 2", ">= 3", ">= 4", ">= 5"],
            RANGE_ENUM: {
                "<= 4": function(items) { return $.grep(items, function(item) {
                    return item.result <= 4;
                });},
                ">= 2": function(items) { return $.grep(items, function(item) {
                    return item.result >= 2;
                });},
                ">= 3": function(items) { return $.grep(items, function(item) {
                    return item.result >= 3;
                });},
                ">= 4": function(items) { return $.grep(items, function(item) {
                    return item.result >= 4;
                });},
                ">= 5": function(items) { return $.grep(items, function(item) {
                    return item.result >= 5;
                });}
            },
            filters: {
                filterYearPrompt: this.i18next.t("Filter By Year"),
                filterResultPrompt: this.i18next.t("Filter By Result"),
                selectedFilterYearValue: "",
                selectedFilterResultRange: "",
                clearLabel: this.i18next.t("Clear Filters")
            },
            showRefresh: false,
            treatment: {
                treatmentTextPrompt: this.i18next.t("Last Received Treatment:"),
                treatmentDatePrompt: this.i18next.t("Treatment Date:"),
                data: []
            },
            modalLoading: false,
            editLink: this.i18next.t("Edit"), 
            editTitle: this.i18next.t("Edit PSA Result"),
            addTitle: this.i18next.t("Add PSA Result")
        },
        computed: {
            yearList: function() {
                var yearList = this.originals.map(function(item) {
                    return item.titleYear;
                });
                yearList = $.grep(yearList, function(item, index) {
                    return yearList.indexOf(item) === index;
                });
                return yearList;
            }
        },
        methods: {
            init: function(dependencies) {
                var self = this;
                dependencies = dependencies || {};
                for(var prop in dependencies) {
                    self[prop] = dependencies[prop];
                }
                sessionStorage.removeItem(this.userIdKey);
                this.getData(true);
                this.getProcedure();
                setTimeout(function() {
                    self.initElementsEvents();
                }, 300);
            },
            refresh: function() {
                this.clearFilter();
                this.getData();
            },
            getRefreshMessage: function() {
                return i18next.t("Click to reload the page and try again.");
            },
            validateResult: function(val) {
                var isValid = !(isNaN(val) || parseInt(val) < 0);
                if(!isValid) {
                    this.addErrorMessage = this.i18next.t("Result must be a number.");
                } else {
                    this.addErrorMessage = "";
                }
                return isValid;
            },
            validateDate: function(date) {
                var isValid = this.tnthDates.isValidDefaultDateFormat(date);
                if(!isValid) {
                    this.addErrorMessage = this.i18next.t("Date must be in the valid format.");
                } else {
                    this.addErrorMessage = "";
                }
                return isValid;
            },
            formatDateString: function(date, format) {
                return this.tnthDates.formatDateString(date, format);
            },
            initElementsEvents: function() {
                var self = this;
                /*
                 * date picker events
                 */
                $("#psaDate").datepicker({
                    "format": "d M yyyy",
                    "forceParse": false,
                    "endDate": new Date(),
                    "maxViewMode": 2,
                    "autoclose": true
                }).on("hide", function() {
                    $("#psaDate").trigger("blur");
                });
                $("#psaDate").on("blur", function() {
                    var newDate = $(this).val();
                    if(newDate) {
                        if(self.validateDate(newDate)) {
                            self.newItem.date = newDate;
                        }
                    }
                }).on("focus", function() {
                    self.modalLoading = false;
                });
                /*
                 * new result field event
                 */
                $("#psaResult").on("change", function() {
                    self.validateResult($(this).val());
                });
                /*
                 * modal event
                 */
                $("#addPSAModal").on("show.bs.modal", function() {
                    self.modalLoading = true;
                });
                $("#addPSAModal").on("shown.bs.modal", function() {
                    $("#psaResult").focus();
                    $("#psaDate").datepicker("update", self.newItem.date||"");
                    setTimeout(function() {
                        self.modalLoading = false; //allow time for setting value with it being visible to user
                    }, 50);
                }).on("hidden.bs.modal", function() {
                    self.clearNew();
                    //$("#psaDate").datepicker("update", "");
                });
            },
            getCurrentUserId: function() {
                var self = this;
                if(!sessionStorage.getItem(this.userIdKey)) {
                    this.tnthAjax.sendRequest("/api/me", "GET", "", { sync: true }, function(data) {
                        if(!data.error) {
                            sessionStorage.setItem(self.userIdKey, data.id);
                        } else {
                            sessionStorage.setItem(self.userIdKey, $("#psaTracker_currentUser").val());
                        }
                    });
                }
                return sessionStorage.getItem(this.userIdKey);
            },
            getExistingItemByDate: function(newDate) {
                var convertedDate = this.tnthDates.formatDateString(newDate, "iso-short"), self = this;
                return $.grep(this.items, function(item) {
                    return convertedDate === self.tnthDates.formatDateString(item.date, "iso-short");
                });
            },
            onEdit: function(item) {
                var self = this;
                if(item) {
                    for(var prop in self.newItem) {
                        if (self.newItem.hasOwnProperty(prop)) {
                            self.newItem[prop] = item[prop];
                        }
                    }
                    setTimeout(function() {
                        $("#addPSAModal").modal("show");
                    }, 250);
                }
            },
            isValidData: function() {
                var newDate = this.newItem.date;
                var newResult = this.newItem.result;
                return newDate && this.validateDate(newDate) && newResult && this.validateResult(newResult);
            },
            onAdd: function() {
                if (!this.isValidData()) {
                    return false;
                }
                this.addErrorMessage = "";
                var existingItem = this.getExistingItemByDate(this.newItem.date);
                if(existingItem.length > 0) {
                    this.newItem.id = existingItem[0].id;
                }
                this.postData();
            },
            getProcedure: function() {
                var self = this;
                this.tnthAjax.getProc(this.getCurrentUserId(), false, function(data) {
                    if (!data || !data.entry || data.entry.length === 0) { return false; }
                    data.entry.sort(function(a, b) {
                        return new Date(b.resource.performedDateTime) - new Date(a.resource.performedDateTime);
                    });
                    var treatmentData = $.grep(data.entry, function(item) {
                        var code = item.resource.code.coding[0].code;
                        return code !== SYSTEM_IDENTIFIER_ENUM.CANCER_TREATMENT_CODE && code !== SYSTEM_IDENTIFIER_ENUM.NONE_TREATMENT_CODE;
                    });
                    if (treatmentData.length === 0) { return false; }
                    self.treatment.data = [treatmentData.map(function(item) {
                        return {
                            "display": item.resource.code.coding[0].display,
                            "date": self.formatDateString(item.resource.performedDateTime.substring(0, 19), "d M y")
                        };
                    })[0]];
                });
            },
            showTreatment: function() {
                return this.treatment.data.length > 0;
            },
            getData: function(isInit) {
                var self = this;
                this.loading = true;
                this.tnthAjax.getClinical(this.getCurrentUserId(), false, function(data) {
                    if(data.error) {
                        $("#psaTrackerErrorMessageContainer").html(self.i18next.t("Error occurred retrieving PSA result data"));
                        self.loading = false;
                        return false;
                    } 
                    if (!data.entry) {
                        $("#psaTrackerErrorMessageContainer").html(self.i18next.t("No result data found"));
                        self.loading = false;
                        return false;
                    }
                    var results = (data.entry).map(function(item) {
                        var dataObj = {}, content = item.content, contentCoding = content.code.coding[0];
                        dataObj.id = content.id;
                        dataObj.code = contentCoding.code;
                        dataObj.display = contentCoding.display;
                        dataObj.updated = self.formatDateString(item.updated.substring(0, 19), "yyyy-mm-dd hh:mm:ss");
                        dataObj.date = self.formatDateString(content.issued.substring(0, 19), "d M y");
                        dataObj.result = content.valueQuantity.value;
                        dataObj.edit = true;
                        dataObj.titleYear = new Date(content.issued).getFullYear();
                        return dataObj;
                    });
                    results = $.grep(results, function(item) {
                        return item.display.toLowerCase() === "psa";
                    });
                    // sort from newest to oldest
                    results = results.sort(function(a, b) {
                        return new Date(b.date) - new Date(a.date);
                    });
                    /*
                     * display only 10 most recent results
                     */
                    if(results.length > 10) {
                        var tempResults = results;
                        results = results.slice(0, 10);
                        self.history.items = tempResults.slice(10);
                    }
                    self.items = self.originals = results;
                    if (!isInit) {
                        self.filterData();
                    }
                    setTimeout(function() {
                        self.drawGraph();
                    }, 500);
                    $("#psaTrackerErrorMessageContainer").html("");
                    setTimeout(function() {
                        self.loading = false;
                    }, 550);
                });
            },
            showHistory: function() {
                $("#PSAHistoryModal").modal("show");
            },
            clearFilter: function() {
                this.filters.selectedFilterResultRange = "";
                this.filters.selectedFilterYearValue = "";
            },
            filterData: function(redraw) {
                var results = this.originals, self = this;
                if (this.filters.selectedFilterYearValue === "") {
                    this.items = this.originals;
                } else {
                    results = $.grep(results, function(item) {
                        return parseInt(item.titleYear) === parseInt(self.filters.selectedFilterYearValue);
                    });
                    this.items = results;
                }
                if (this.filters.selectedFilterResultRange) {
                    this.items = this.RANGE_ENUM[this.filters.selectedFilterResultRange](this.items);
                }
                this.showRefresh = true;
                if (!redraw) {
                    return false;
                }
                setTimeout(function() {
                    self.drawGraph();
                }, 500);
            },
            filterDataByYearEvent: function(event) {
                this.filters.selectedFilterYearValue = event.target.value;
                this.filterData(true);
            },
            filterDataByResultEvent: function(event) {
                this.filters.selectedFilterResultRange = event.target.value;
                this.filterData(true);
            },
            showFilters: function() {
                return this.originals.length > 1;
            }, 
            postData: function() {
                var cDate = "";
                var self = this;
                var userId = this.getCurrentUserId();
                if(this.newItem.date) {
                    var dt = new Date(this.newItem.date);
                    // in 2017-07-06T12:00:00 format
                    cDate = [dt.getFullYear(), (dt.getMonth() + 1), dt.getDate()].join("-");
                    cDate = cDate + "T12:00:00";
                }
                var url = "/api/patient/" + userId + "/clinical";
                var method = "POST";
                var obsCode = [{ "code": this.clinicalCode, "display": this.clinicalDisplay, "system": this.clinicalSystem }];
                var obsArray = {};
                obsArray["resourceType"] = "Observation";
                obsArray["code"] = { "coding": obsCode };
                obsArray["issued"] = cDate;
                obsArray["valueQuantity"] = { "units": "g/dl", "code": "g/dl", "value": this.newItem.result };

                if(this.newItem.id) {
                    method = "PUT";
                    url = url + "/" + this.newItem.id;
                }

                this.tnthAjax.sendRequest(url, method, userId, { data: JSON.stringify(obsArray) }, function(data) {
                    if(data.error) {
                        self.addErrorMessage = self.i18next.t("Server error occurred adding PSA result.");
                    } else {
                        $("#addPSAModal").modal("hide");
                        self.getData();
                        self.clearNew();
                        self.addErrorMessage = "";
                    }
                });
            },
            clearNew: function() {
                var self = this;
                for(var prop in self.newItem) {
                    if (self.newItem.hasOwnProperty(prop)) {
                        self.newItem[prop] = "";
                    }
                }
            },
            drawGraph: function() {
                /*
                 * using d3 to draw graph
                 */
                $("#psaTrackerGraph").html("");
                var self = this;
                var d3 = self.d3;
                var i18next = self.i18next;
                var WIDTH = 600,
                    HEIGHT = 430,
                    TOP = 50,
                    RIGHT = 40,
                    BOTTOM = 110,
                    LEFT = 60,
                    TIME_FORMAT = "%d %b %Y";

                // Set the dimensions of the canvas / graph
                var margin = { top: TOP, right: RIGHT, bottom: BOTTOM, left: LEFT },
                    width = WIDTH - margin.left - margin.right,
                    height = HEIGHT - margin.top - margin.bottom;

                var timeFormat = d3.time.format(TIME_FORMAT);
                // Parse the date / time func
                var parseDate = timeFormat.parse;

                var data = self.items;

                data.forEach(function(d) {
                    d.graph_date = parseDate(d.date);
                    d.result = isNaN(d.result) ? 0 : +d.result;
                });

                var minDate = d3.min(data, function(d) {
                    return d.graph_date;
                });
                var maxDate = d3.max(data, function(d) {
                    return d.graph_date;
                });

                if (data.length === 1 || String(minDate) === String(maxDate)) {
                    var firstDate = new Date(minDate);
                    maxDate = new Date(firstDate.setDate(firstDate.getDate() + 365));
                }
        
                var treatmentDate;
                if (self.treatment.data.length > 0) {
                    treatmentDate = parseDate(self.treatment.data[0].date);
                }
                var xDomain = d3.extent(data, function(d) { return d.graph_date; });
                var bound = (width - margin.left - margin.right) / 10;
                var x = d3.time.scale().range([bound, width - bound]);
                var y = d3.scale.linear().range([height, 0]);
                var DAY = 1000 * 60 * 60 * 24;
                var DIFF = (new Date(maxDate) - new Date(minDate)) / DAY;
                var INTERVAL = Math.ceil(DIFF / 9);

                function handleTreatmentDate(minDate, maxDate) {
                    var startMinDate, startMaxDate;
                    if (minDate && treatmentDate.getTime() < minDate.getTime()) {
                        startMinDate = new Date(minDate);
                        treatmentDate = new Date(startMinDate.setUTCDate(startMinDate.getUTCDate() - Math.floor(INTERVAL/2)));
                    }
                    if (maxDate && treatmentDate.getTime() > maxDate.getTime()) {
                        startMaxDate = new Date(maxDate);
                        treatmentDate =  new Date(startMaxDate.setUTCDate(startMaxDate.getUTCDate() + Math.floor(INTERVAL/2)));
                    }
                }

                function customTickFunc(t0, t1) {
                    var startTime = new Date(t0), endTime = new Date(t1), times = [], lastInterval, dateTime;
                    startTime.setUTCDate(startTime.getUTCDate());
                    endTime.setUTCDate(endTime.getUTCDate());
                    while(startTime <= endTime) {
                        dateTime = new Date(startTime);
                        startTime.setUTCDate(startTime.getUTCDate() + INTERVAL);
                        lastInterval = (new Date(startTime) - new Date(endTime)) / DAY;
                        times.push(dateTime);
                    }
                    if (startTime > endTime && (Math.ceil(lastInterval) < INTERVAL / 2)) {
                        times.push(new Date(startTime));
                        maxDate = new Date(startTime);
                    }
                    return times;
                }

                // Scale the range of the data
                var endY = Math.max(10, d3.max(data, function(d) { return d.result; }));

                if(data.length === 1) {
                    //var firstDate = new Date(data[0].graph_date);
                    //xDomain = [data[0].graph_date, new Date(firstDate.setDate(firstDate.getDate() + 365))];
                    xDomain = [data[0].graph_date, maxDate];
                }

                x.domain(xDomain);
                y.domain([0, parseInt(endY + (endY / (data.length + 1)))]);

                // Define the axes
                var xAxis = d3.svg.axis()
                    .scale(x)
                    .orient("bottom")
                    .ticks(customTickFunc)
                    .tickSize(0, 0, 0)
                    .tickFormat(timeFormat);

                var yAxis = d3.svg.axis()
                    .scale(y)
                    .ticks(5)
                    .orient("left")
                    .tickSize(0, 0, 0);

                // Define the line
                var valueline = d3.svg.line()
                    .interpolate("linear")
                    .x(function(d) { return x(d.graph_date); })
                    .y(function(d) { return y(d.result); });

                // Adds the svg canvas
                var svg = d3.select("#psaTrackerGraph")
                    .append("svg")
                    .attr("width", width + margin.left + margin.right)
                    .attr("height", height + margin.top + margin.bottom);
                //background
                svg.append("rect")
                    .attr("x", margin.left)
                    .attr("y", margin.top)
                    .attr("width", width)
                    .attr("height", height)
                    .style("stroke", "#777")
                    .style("stroke-width", "1")
                    .style("fill", "hsla(0, 0%, 93%, 0.7)");

                var graphArea = svg.append("g").attr("transform", "translate(" + margin.left + "," + margin.top + ")");

                // Add the X Axis
                graphArea.append("g")
                    .attr("class", "x axis x-axis")
                    .attr("transform", "translate(0," + height + ")")
                    .call(xAxis)
                    .selectAll("text")
                    .attr("y", 0)
                    .attr("x", 7)
                    .attr("dy", ".35em")
                    .attr("transform", "rotate(90)")
                    .attr("class", "axis-stroke")
                    .style("text-anchor", "start");

                // Add the Y Axis
                graphArea.append("g")
                    .attr("class", "y axis y-axis")
                    .call(yAxis)
                    .selectAll("text")
                    .attr("dx", "-2px")
                    .attr("dy", "6px")
                    .attr("class", "axis-stroke")
                    .style("text-anchor", "end");

                // add the X gridlines
                graphArea.append("g")
                    .attr("class", "grid grid-x")
                    .attr("transform", "translate(0," + height + ")")
                    .call(xAxis
                        .tickSize(-height)
                        .tickFormat("")
                    );
                // add the Y gridlines
                graphArea.append("g")
                    .attr("class", "grid grid-y")
                    .call(yAxis
                        .tickSize(-width)
                        .tickFormat("")
                    );

                //add div for tooltip
                var tooltipContainer = d3.select("body").append("div").attr("class", "tooltip").style("opacity", 0);


                //treatment line
                if (treatmentDate) {
                    handleTreatmentDate(minDate, maxDate);
                    var treatmentPath = graphArea.append("path");
                    treatmentPath.attr("d", "M"+x(treatmentDate) + " 0" + " V " + height + " Z")
                        .style("stroke", "#8b6e3c80")
                        .style("stroke-dasharray", "1, 5")
                        .style("stroke-width", "2");

                    graphArea.append("use")
                        .attr("x", x(treatmentDate) - 2)
                        .attr("y", -2)
                        .attr("xlink:href", "#marker");

                    graphArea.append("use")
                        .attr("x", x(treatmentDate) + 6)
                        .attr("y", height - 6)
                        .attr("xlink:href", "#arrow");
                   
                    var RECT_HEIGHT = 25, RECT_WIDTH = 70;
                    graphArea.append("rect")
                        .attr("x", x(treatmentDate) - RECT_WIDTH/2)
                        .attr("y", 25)
                        .attr("width", RECT_WIDTH)
                        .attr("height", RECT_HEIGHT)
                        .style("stroke", "#777")
                        .style("stroke-width", "0.5")
                        .style("fill", "#FFF")
                        .classed("treatment-rect", true);
                    graphArea.append("text")
                        .attr("x", x(treatmentDate))
                        .attr("y", 40)
                        .attr("text-anchor", "middle")
                        .attr("font-size", "10px")
                        .style("stroke-width", "4")
                        .style("fill", "#8a6d3b")
                        .style("letter-spacing", "2px")
                        .text(i18next.t("treatment"));
                }
               
                // Add the valueline path.
                graphArea.append("path")
                    .attr("class", "line")
                    .style("stroke", "#8b8ea2")
                    .attr("d", valueline(data));

                // Add the scatterplot
                var circleRadius = 3.7;
                graphArea.selectAll("circle").data(data)
                    .enter().append("circle")
                    .transition()
                    .duration(850)
                    .delay(function(d, i) { return i * 3; })
                    .attr("r", circleRadius)
                    .attr("class", "circle")
                    .attr("cx", function(d) { return x(d.graph_date); })
                    .attr("cy", function(d) { return y(d.result); });
                graphArea.selectAll("circle")
                    .on("mouseover", function(d) {
                        var element = d3.select(this);
                        element.transition().duration(100).attr("r", circleRadius * 2);
                        element.style("stroke", "#FFF")
                            .style("stroke-width", "2")
                            .style("fill", "#777")
                            .classed("focused", true);
                        d3.select("#psaTrackerResultsTable tr[data-id='" + d.id + "']").classed("selected", true);
                        tooltipContainer.transition().duration(200).style("opacity", .9);
                        tooltipContainer.html(d.result + "<br/>" + d.date)
                            .style("width", (String(d.date).length*8 + 10) + "px")
                            .style("height", 35 + "px")
                            .style("left", (d3.event.pageX - 48) + "px")     
                            .style("top", (d3.event.pageY - 48) + "px");  
                    })
                    .on("mouseout", function(d) {
                        var element = d3.select(this);
                        element.transition()
                            .duration(100)
                            .attr("r", circleRadius);
                        element.style("stroke", "#777")
                            .style("stroke-width", "1")
                            .style("fill", "#FFF")
                            .classed("focused", false);
                        d3.select("#psaTrackerResultsTable tr[data-id='" + d.id + "']").classed("selected", false);
                        tooltipContainer.transition().duration(500).style("opacity", 0);   
                    })
                    .on("click", self.onEdit);

                // Add text labels
                graphArea.selectAll("text.text-label")
                    .data(data)
                    .enter()
                    .append("text")
                    .classed("text-label", true)
                    .attr("x", function(d) {
                        return x(d.graph_date);
                    })
                    .attr("y", function(d) {
                        return y(d.result);
                    })
                    .attr("text-anchor", "middle")
                    .attr("dy", "-1em")
                    .attr("font-size", "11px")
                    .style("stroke-width", "2")
                    .attr("font-weight", "900")
                    .attr("letter-spacing", "1px")
                    .attr("fill", "darkgreen")
                    .text(function(d) {
                        return d.result;
                    });

                // Add caption
                graphArea.append("text")
                    .attr("x", (width / 2))
                    .attr("y", 0 - (margin.top / 2))
                    .attr("text-anchor", "middle")
                    .attr("class", "graph-caption")
                    .text("PSA (ng/ml)");

                //add axis legends
                var xlegend = graphArea.append("g")
                    .attr("transform", "translate(" + (width / 2 - margin.left + margin.right - 20) + "," + (height + margin.bottom - margin.bottom / 8 + 5) + ")");

                xlegend.append("text")
                    .text(i18next.t("PSA Test Date"))
                    .attr("class", "legend-text");

                var ylegend = graphArea.append("g")
                    .attr("transform", "translate(" + (-margin.left + margin.left / 2.5) + "," + (height / 2 + height / 6) + ")");

                ylegend.append("text")
                    .attr("transform", "rotate(270)")
                    .attr("class", "legend-text")
                    .text(i18next.t("Result (ng/ml)"));

            }
        }
    });
    $(function() { /*global $ tnthDates, tnthAjax, SYSTEM_IDENTIFIER_ENUM, i18next, d3 */
        psaApp.init({ tnthDates: tnthDates, tnthAjax: tnthAjax, SYSTEM_IDENTIFIER_ENUM: SYSTEM_IDENTIFIER_ENUM, i18next: i18next, d3: d3 });
    });
})();

<template>
    <div>
        <div class="modal fade" id="dataDownloadModal" tabindex="-1" role="dialog">
            <div class="modal-dialog modal-dialog-centered" role="document">
                <div class="modal-content">
                    <div class="modal-header">
                        <button type="button" class="close" data-dismiss="modal" :aria-label="closeLabel"><span aria-hidden="true">&times;</span></button>
                        <span v-text="title"></span>
                    </div>
                    <div class="modal-body">
                        <div class="form-group">
                            <!-- radio buttons selector for either main study or sub-study instruments -->
                            <div id="studyListSelector" class="list-selector sub-study">
                                <div class="items">
                                    <div class="item">
                                        <input type="radio" name="listSelector" @click="setCurrentMainStudy()" checked>
                                        <span class="text" v-text="mainStudySelectorLabel" :class="{'active': isCurrentMainStudy()}"></span>
                                    </div>
                                    <div class="item">
                                        <input type="radio" name="listSelector" @click="setCurrentSubStudy()">
                                        <span class="text" v-text="subStudySelectorLabel" :class="{'active': isCurrentSubStudy()}"></span>
                                    </div>
                                </div>
                            </div>
                            <label class="text-muted prompt" v-text="instrumentsPromptLabel"></label>
                            <div id="patientsInstrumentListWrapper">
                                <!-- dynamically load instruments list -->
                                <div id="patientsInstrumentList" class="profile-radio-list">
                                    <div v-show="isCurrentMainStudy()">
                                        <div class="list">
                                            <div class="checkbox instrument-container" :id="code+'_container'" v-for="code in mainStudyInstrumentsList"><label><input type="checkbox" name="instrument" :value="code">{{getDisplayInstrumentName(code)}}</label></div>
                                        </div>
                                    </div>
                                    <!-- sub-study instrument list, should only display when the user is part of the sub-study -->
                                    <div v-show="isCurrentSubStudy()">
                                        <div class="list">
                                            <div class="checkbox instrument-container" :id="code+'_container'" v-for="code in subStudyInstrumentsList"><label><input type="checkbox" name="instrument" :value="code">{{getDisplayInstrumentName(code)}}</label></div>
                                        </div>
                                    </div>
                                </div>
                                <div id="instrumentListLoad"><i class="fa fa-spinner fa-spin fa-2x loading-message"></i></div>
                            </div>
                        </div>
                        <div class="form-group data-types-container">
                            <label class="text-muted prompt" v-text="dataTypesPromptLabel"></label>
                            <div id="patientsDownloadTypeList" class="profile-radio-list">
                                <label class="radio-inline" v-for="item in dataTypes" :key="item.id" :class="{'active': item.value == 'csv'}">
                                    <input type="radio" name="downloadType" :id="item.id" :value="item.value" @click="setDataType" :checked="item.value == 'csv'" />
                                    {{item.label}}
                                </label>
                            </div>
                        </div>
                        <div id="instrumentsExportErrorMessage" class="error-message"></div>
                        <!-- display export status -->
                        <ExportDataLoader ref="exportDataLoader" :initElementId="getInitElementId()" :exportUrl="getExportUrl()" v-on:initExportCustomEvent="initExportEvent"></ExportDataLoader>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-default" id="patientsDownloadButton" :disabled="!hasInstrumentsSelection()" v-text="exportLabel"></button>
                        <button type="button" class="btn btn-default" data-dismiss="modal" v-text="closeLabel"></button>
                    </div>
                </div>
            </div>
        </div>
        <div id="patientListExportDataContainer">
            <a href="#" id="patientAssessmentDownload"  class="btn btn-tnth-primary" data-toggle="modal" data-target="#dataDownloadModal"><span v-text="title" /></a>
        </div>
    </div>
</template>
<script>
    import Global from "../modules/Global.js";
    import tnthAjax from "../modules/TnthAjax.js";
    import {EPROMS_SUBSTUDY_QUESTIONNAIRE_IDENTIFIER} from "../data/common/consts.js";
    import ExportInstrumentsData from "../data/common/ExportInstrumentsData.js";
    import ExportDataLoader from "./asyncExportDataLoader.vue";
    export default { /*global i18next */
        components: {ExportDataLoader},
        data: function() {
            return {...ExportInstrumentsData, ...{
                currentStudy: "main",
                mainStudyIdentifier: "main",
                subStudyIdentifier: "substudy",
                mainStudyInstrumentsList:[],
                subStudyInstrumentsList:[]
            }};
        },
        mounted: function() {
            this.getInstrumentList();
        },
        methods: {
            getInitElementId: function() {
                return "patientsDownloadButton";
            },
            setCurrentStudy: function(identifier) {
                if (!identifier) return;
                this.currentStudy = identifier;
            },
            setCurrentMainStudy: function() {
                this.setCurrentStudy(this.mainStudyIdentifier);
            },
            setCurrentSubStudy: function() {
                this.setCurrentStudy(this.subStudyIdentifier);
            },
            isCurrentMainStudy: function() {
                return this.currentStudy === this.mainStudyIdentifier;
            },
            isCurrentSubStudy: function() {
                return this.currentStudy === this.subStudyIdentifier;
            },
            setErrorMessage: function(message) {
                document.querySelector("#instrumentsExportErrorMessage").innerText = message;
            },
            getInstrumentList: function () {
                var self = this;
                //set sub-study elements vis
                Global.setSubstudyElementsVis(".sub-study", (data) => {
                    tnthAjax.getInstrumentsList(false, function (data) {
                        if (!data || !data.length) {
                            self.setErrorMessage(data.error);
                            self.setInstrumentsListReady();
                            return false;
                        }
                        self.setErrorMessage("");
                        let entries = data.sort();
                        self.setMainStudyInstrumentsListContent(entries);
                        self.setSubStuyInstrumentsListContent(entries);
                        self.setInstrumentsListReady();
                        setTimeout(function() {
                            self.setInstrumentInputEvent();
                        }.bind(self), 150);
                    });
                });
            },
            isSubStudyInstrument: function(instrument_code) {
                if (!instrument_code) return false;
                let re = new RegExp(EPROMS_SUBSTUDY_QUESTIONNAIRE_IDENTIFIER, "i");
                if (re.test(instrument_code)) {
                    return true;
                }
            },
            setMainStudyInstrumentsListContent: function(list) {
                if (!list) return false;
                this.mainStudyInstrumentsList = list.filter(code => {
                    return !this.isSubStudyInstrument(code);
                });
            },
            setSubStuyInstrumentsListContent: function(list) {
                if (!list) return false;
                this.subStudyInstrumentsList = list.filter(code => {
                    return this.isSubStudyInstrument(code);
                });
            },
            getDisplayInstrumentName: function(code) {
                if (!code) return "";
                return code.replace(/_/g, " ").toUpperCase();
            },
            setInstrumentInputEvent: function() {
                var self = this;
                $("#patientsInstrumentList [name='instrument']").on("click", function(event) {
                    self.instruments.selected = "";
                    let arrSelected = [];
                    $("input[name=instrument]").each(function() {
                        if ($(this).is(":checked")) {
                            arrSelected.push($(this).val());
                            $(this).closest("label").addClass("active");
                        } else $(this).closest("label").removeClass("active");
                    });
                    if (!arrSelected.length) {
                        self.instruments.selected = "";
                        return;
                    }
                    self.instruments.selected = arrSelected.map(item => `instrument_id=${item}`).join("&");
                });
                $("#patientsInstrumentList [name='instrument'], #patientsDownloadTypeList [name='downloadType']").on("click", function() {
                    //clear pre-existing error
                    self.resetExportError();
                });
                //study selector onclick event
                $("#studyListSelector [name='listSelector']").on("click", function() {
                    //clear pre-existing error
                    self.resetExportError();
                    self.resetInstrumentSelections();
                });
                //patientsDownloadTypeList downloadType
                $("#patientsDownloadTypeList [name='downloadType']").on("click", function() {
                    $("#patientsDownloadTypeList label").removeClass("active");
                    if ($(this).is(":checked")) {
                        $(this).closest("label").addClass("active");
                        return;
                    }
                });
                $("#dataDownloadModal").on("show.bs.modal", function () {
                    self.instruments.selected = "";
                    self.instruments.dataType = "csv";
                    self.resetExportError();
                    self.setInstrumentsListReady();
                    $(this).find("[name='instrument']").prop("checked", false);
                });
            },
            resetExportError: function() {
                this.$refs.exportDataLoader.clearExportDataUI();
            },
            initExportEvent: function() {
                /*
                 * custom UI events associated with exporting data
                 */
                let self = this;
                 $("#dataDownloadModal").on("hide.bs.modal", function () {
                    $("#"+self.getInitElementId()).removeAttr("data-export-in-progress");
                });
            },
            setDataType: function (event) {
                this.instruments.showMessage = false;
                this.instruments.dataType = event.target.value;
            },
            resetInstrumentSelections: function() {
                $("#patientsInstrumentList [name='instrument']").prop("checked", false);
                $("#patientsInstrumentList label").removeClass("active");
                this.instruments.selected = "";
            },
            setInstrumentsListReady: function() {
                Vue.nextTick(function() {
                    document.querySelector("#patientsInstrumentList").classList.add("ready");
                });
            },
            hasInstrumentsSelection: function () {
                return this.instruments.selected !== "" && this.instruments.dataType !== "";
            },
            getExportUrl: function() {
                return `/api/patient/assessment?${this.instruments.selected}&format=${this.instruments.dataType}`;
            },
        }
    };
</script>

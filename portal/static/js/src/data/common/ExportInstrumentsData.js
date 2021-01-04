export default {
    title: i18next.t("Export questionnaire data"),
    closeLabel: i18next.t("Close"),
    exportLabel: i18next.t("Export"),
    mainStudySelectorLabel: i18next.t("Main Study"),
    subStudySelectorLabel: i18next.t("Sub-Study"),
    dataTypesPromptLabel: i18next.t("Data type:"),
    instrumentsPromptLabel: i18next.t("Instrument(s) to export data from:"),
    dataTypes: [
        {
            id: "csv_dataType",
            value: "csv",
            label: i18next.t("CSV")
        },
        {
            id: "json_dataType",
            value: "json",
            label: i18next.t("JSON")
        }
    ],
    instruments: {
        list: [],
        dataType: "csv",
        selected: "",
        message: ""
    },
    requestSubmittedDisplay: i18next.t("Export request submitted"),
    failedRequestDisplay: i18next.t("Request to export data failed.")
};

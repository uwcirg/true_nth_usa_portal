export default {
    userId: $("#_report_user_id").val(),
    reportDate: $("#_report_authored_date").val(),
    instrumentId: $("#_report_instrument_id").val(),
    errorMessage: "",
    data: [],
    tableHeaders: [i18next.t("Question"), i18next.t("Response")],
    caption: {},
    serverError: i18next.t("Server Error occurred retrieving report data"),
    noDataError: i18next.t("No data returned from server"),
    loadError: i18next.t("Unable to load report data")
};

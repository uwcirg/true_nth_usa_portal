$(".button-container").each(function() {
    $(this).prepend('<div class="loading-message-indicator"><i class="fa fa-spinner fa-spin fa-2x"></i></div>');
});
$(".btn-tnth-primary").on("click", function() {
    if ($(this).hasClass("disabled")) {
        return false;
    }
    var link = $(this).attr("href");
    if (link) {
        event.preventDefault();
        $(this).hide();
        $(this).prev(".loading-message-indicator").show();
        setTimeout(function() {
            window.location=link;
        }, 300);
    }
});
$(document).on("ready", function() {
    $("body").addClass("portal");
});



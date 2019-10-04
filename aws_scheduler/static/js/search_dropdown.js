$(document).ready(function() {
    $(".js-select2").select2();

    const quickFormRds = document.querySelector(".quick-schedule__form_rds");

    if (quickFormRds) {
        let dbInstancearn, region;

        $(".js-select2").on("select2:select", ({params}) => {
            region = params.data.element.dataset.region;
            dbInstancearn = params.data.element.dataset.dbinstancearn;
        });

        quickFormRds.addEventListener("submit", () => {
            quickFormRds.action = `/rds/regions/${region}/instances/${dbInstancearn}/tags/add`;
        });
    }
});

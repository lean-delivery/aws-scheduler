$(document).ready(function() {
    $(".js-select2").select2();

    const quickFormRds = document.querySelector(".quick-schedule__form_rds") || null;
    const buttonQuickFormRds = quickFormRds.querySelector(".button");

    if (quickFormRds) {
        let dbInstancearn, region;

        $(".js-select2").on("select2:select", ({params}) => {
            region = params.data.element.dataset.region;
            dbInstancearn = params.data.element.dataset.dbinstancearn;

            buttonQuickFormRds.classList.remove("button__disabled");
        });

        quickFormRds.addEventListener("submit", () => {
            quickFormRds.action = `/rds/regions/${region}/instances/${dbInstancearn}/tags/add`;
        });
    }
});

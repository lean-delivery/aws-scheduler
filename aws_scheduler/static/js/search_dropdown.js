$(document).ready(function() {
    const quickForm = document.querySelector(".quick-schedule__form");

    let region = null;
    let dbInstancearn = null;

    $(".js-select2").select2();

    $(".select2-form").on("select2:select", (evt) => {
        const { currentTarget, params, target } = evt;
        const arrayElementSelect = [...currentTarget.querySelectorAll(".js-select2")];
        const isSelected = arrayElementSelect.every(item => item.selectedIndex !== 0);

        if (isSelected) {
            currentTarget.querySelector(".button").classList.remove("button__disabled");
        }

        if (target.classList.contains("js-select2-instance")) {
            region = params.data.element.dataset.region;
            dbInstancearn = params.data.element.dataset.dbinstancearn;
        }
    });

    quickForm.addEventListener("submit", () => {
        if (region && dbInstancearn) {
            quickForm.action = `/rds/regions/${region}/instances/${dbInstancearn}/tags/add`;
        }
    });
});

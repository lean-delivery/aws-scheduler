$(document).ready(function() {
    const select2 = $(".js-select2");
    const quickFormRds = document.querySelector(".quick-schedule__form");

    let region = null;
    let dbInstancearn = null;
    let countSelectBlock = 0;



    const findParentByClassName = (element, tag) => {
        while (element.tagName !== tag.toUpperCase()
            ) {
            if (element.tagName === "BODY") return null;
            element = element.parentNode;
        }
        return element;
    };

    $(".js-select2-instance").on("select2:select", ({params}) => {
        region = params.data.element.dataset.region;
        dbInstancearn = params.data.element.dataset.dbinstancearn;
    });

    quickFormRds.addEventListener("submit", () => {
        quickFormRds.action = `/rds/regions/${region}/instances/${dbInstancearn}/tags/add`;
    });

    select2.select2().on("select2:select", ({target}) => {
        const form = findParentByClassName(target, "form");
        const countSelectForm = form.querySelectorAll(".js-select2").length;

        countSelectBlock += 1;

        if (countSelectForm === countSelectBlock) {
            countSelectBlock = 0;
            const form = findParentByClassName(target, "form");

            form.querySelector(".button").classList.remove("button__disabled");
        }
    });
});

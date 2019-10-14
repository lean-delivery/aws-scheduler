$(document).ready(function() {
    const quickForm = document.querySelector(".quick-schedule__form");

    let region = null;
    let dbInstancearn = null;
    let valueSchedule = null;

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

    $(".js-select2-schedule").on("select2:select", ({params}) => {
        valueSchedule = params.data.element.value;
    });

    quickForm.addEventListener("submit", () => {
        const url = `/rds/regions/${region}/instances/${dbInstancearn}/tags/add`;

        callSchedule({url, valueSchedule})
    });

    function callSchedule({url = "/", method = "POST", valueSchedule}) {
        const xhr = new XMLHttpRequest();
        xhr.open(method, url, false);

        if (method === "POST") {
            xhr.setRequestHeader("Content-Type", "application/json");
        }

        console.log(valueSchedule)

        xhr.send(JSON.stringify({
            "Key": "Schedule",
            "Value": valueSchedule
        }));
    }
});

$(document).ready(function() {
    const quickForm = document.querySelector(".quick-schedule__form");
    const rdsInstancFormAdd = document.querySelectorAll(".instances__form");
    const rdsInstancFormRemove = document.querySelectorAll(".instance-form-remove");

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

    const handleSubmitAdd = (evt) => {
        if (region && dbInstancearn) {
            evt.preventDefault();

            const url = `/rds/regions/${region}/instances/${dbInstancearn}/tags/add`;

            callSchedule({url, valueSchedule})
        }
    };

    const handleSubmitRemove = (evt) => {
        const input = evt.target.querySelectorAll("input");
        const [dbInstancearnElement, regionElement, valueScheduleElement] = input;
        [region, dbInstancearn, valueSchedule] = [regionElement.value, dbInstancearnElement.value, valueScheduleElement.value];

        if (region && dbInstancearn) {
            evt.preventDefault();

            const url = `/rds/regions/${region}/instances/${dbInstancearn}/tags/remove`;

            callSchedule({url, valueSchedule})
        }
    };

    quickForm.addEventListener("submit", handleSubmitAdd);

    rdsInstancFormAdd.forEach((item) => {
        item.addEventListener("submit", handleSubmitAdd);
    });

    rdsInstancFormRemove.forEach((item) => {
        item.addEventListener("submit", handleSubmitRemove);
    });

    function callSchedule({url = "/", method = "POST", valueSchedule}) {
        const xhr = new XMLHttpRequest();
        xhr.open(method, url, false);

        if (method === "POST") {
            xhr.setRequestHeader("Content-Type", "application/json");
        }

        xhr.onreadystatechange = () => {
            if (xhr.readyState !== 4) return;

            if (xhr.status === 200) {
                window.location.reload();
            }
        };

        xhr.send(JSON.stringify({
            "Key": "Schedule",
            "Value": valueSchedule
        }));
    }
});

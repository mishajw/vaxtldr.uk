var DOSE_COLORS = {
    "1": "rgb(255, 205, 86)",
    "2": "rgb(75, 192, 192)",
};
var DOSE_LABELS = {
    "1": "1st dose",
    "2": "2nd dose",
};

function start() {
    d3.csv("data.csv").then(makeChart);
}

function makeChart(csv) {
    var groups = csv.map(function (row) { return row.group; }).filter(distinct);
    // var doses = csv.map(function (row) { return row.dose; }).filter(distinct);
    var doses = ["2", "1"];
    var vaccinated_per_dose = doses.map(function(dose) {
        var vaccinated = csv
            .filter(function(row) { return row.dose == dose; })
            .map(function(row) { return parseInt(row.vaccinated); });
        return {
            label: DOSE_LABELS[dose],
            backgroundColor: DOSE_COLORS[dose],
            data: vaccinated,
        };
    });

    var chart = new Chart("chart", {
        type: "horizontalBar",
        data: {
            labels: groups,
            datasets: vaccinated_per_dose,
        },
        options: {
            scales: {
                yAxes: [{stacked: true}],
                xAxes: [{stacked: false}],
            }
        }
    });
}

function distinct(value, index, self) {
  return self.indexOf(value) === index;
}

window.addEventListener("load", start);
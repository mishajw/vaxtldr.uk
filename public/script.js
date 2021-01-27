var DOSE_COLORS = {
    "1": "rgb(255, 205, 86)",
    "2": "rgb(75, 192, 192)",
};
var DOSE_LABELS = {
    "1": "1st dose",
    "2": "2nd dose",
};

function start() {
    d3.csv("latest.csv").then(initialiseCharts);
}

function initialiseCharts(csv) {
//    var groups = csv.map(function (row) { return row.group; }).filter(distinct);
    var annotation = {
        drawTime: "afterDatasetsDraw",
        annotations: [{
            type: "line",
            display: true,
            scaleID: "x",
            value: '82',
            borderColor: "orange",
            borderWidth: 2,
            label: {
                content: "Herd immunity",
                enabled: true,
                position: "left",
            }
        }]
    };
    makeChart(
        "bar-all",
        "Percent of UK vaccinated",
        csv.filter(function (row) { return row.group == "all"; }),
        annotation)
    makeChart(
        "bar-over-80",
        "Percent of >80s vaccinated",
        csv.filter(function (row) { return row.group == ">=80"; }),
        {})
}

function makeChart(id, title, csv, annotation) {
    var doses = csv.map(function (row) { return row.dose; }).filter(distinct);
    var vaccinated_per_dose = doses.map(function(dose) {
        // TODO: Unnest function.
        var vaccinated = csv
            .filter(function(row) { return row.dose == dose; })
            .map(function(row) {
                var vaccinated = parseInt(row.vaccinated);
                var population = parseFloat(row.population);
                return {
                    x: (vaccinated / population) * 100,
                    vaccinated: vaccinated,
                    population: population,
                };
            });
        return {
            label: DOSE_LABELS[dose],
            backgroundColor: DOSE_COLORS[dose],
            data: vaccinated,
        };
    });
    var chart = new Chart(id, {
        type: "horizontalBar",
        data: {
            labels: [title],
            datasets: vaccinated_per_dose,
        },
        options: {
            title: {
                text: title,
                fontSize: 24,
                display: true,
            },
            tooltips: {
                callbacks: {
                    label: function(tooltipItem, data) {
                        var dataset = data.datasets[tooltipItem.datasetIndex]
                        var data = dataset.data[tooltipItem.index];
                        return dataset.label + ": "
                            + data.x.toFixed(2) + "%"
                            + " (" + formatPopulation(data.vaccinated)
                            + " of " + formatPopulation(data.population) + ")";
                    }
                }
            },
            scales: {
                yAxes: [{
                    stacked: true,
                    ticks: {display: false}
                }],
                xAxes: [{
                    id: 'x',
                    stacked: false,
                    ticks: {
                        min: 0,
                        max: 100,
                        callback: function (value) {
                            return value + "%"
                        }
                    }
                }],
            },
            annotation: annotation,
        }
    });
}

function distinct(value, index, self) {
  return self.indexOf(value) === index;
}

function formatPopulation(number) {
    if (number < 1000) {
        return toString(number);
    } else if (number < 1_000_000) {
        return (number / 1000).toFixed(1) + "k";
    } else if (number < 1_000_000_000) {
        return (number / 1_000_000).toFixed(1) + "m";
    } else {
        return "LARGE";
    }
}

window.addEventListener("load", start);
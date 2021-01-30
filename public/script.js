var DOSES = ["2_wait", "2", "1"];
var DOSE_COLORS = {
    "2_wait": "#205072",
    "2": "#56C596",
    "1": "#CFF4D2",
};
var DOSE_LABELS = {
    "2_wait": "2nd dose + 2 weeks",
    "2": "2nd dose",
    "1": "1st dose",
};

function start() {
    d3.csv("latest.csv").then(initializeBarCharts);
    d3.csv("line.csv").then(initializeLineChart);
}

function initializeBarCharts(csv) {
    var annotation = {
        drawTime: "afterDatasetsDraw",
        annotations: [{
            type: "line",
            display: true,
            scaleID: "x",
            value: '70',
            borderColor: "orange",
            borderWidth: 2,
            label: {
                content: "Herd immunity\u00B9",
                enabled: true,
                xAdjust: 55,
            }
        }]
    };
    makeBarChart(
        "bar-all",
        "Percent of UK vaccinated",
        csv.filter(function (row) { return row.group == "all"; }),
        annotation);
    makeBarChart(
        "bar-over-80",
        "Percent of >80s\u00B2 vaccinated",
        csv.filter(function (row) { return row.group == ">=80"; }),
        {});
}

function makeBarChart(id, title, csv, annotation) {
    var vaccinated_per_dose = DOSES.map(function(dose) {
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

function initializeLineChart(csv) {
    var dates = csv
        .map(function (row) { return row.real_date; })
        .filter(distinct);
    var datasets = DOSES.map(function (dose) {
        var vaccinated = csv
            .filter(function(row) { return row.dose == dose; })
            .map(function(row) {
                var vaccinated = parseInt(row.vaccinated);
                var population = parseFloat(row.population);
                return {
                    x: row.real_date,
                    y: (vaccinated / population) * 100,
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

    var chart = new Chart("line", {
        type: "line",
        data: {
            labels: dates,
            datasets: datasets,
        },
        options: {
            title: {
                text: "UK vaccinated over time",
                fontSize: 24,
                display: true,
            },
            tooltips: {
                callbacks: {
                    label: function(tooltipItem, data) {
                        var dataset = data.datasets[tooltipItem.datasetIndex]
                        var data = dataset.data[tooltipItem.index];
                        return dataset.label + ": "
                            + data.y.toFixed(2) + "%"
                            + " (" + formatPopulation(data.vaccinated)
                            + " of " + formatPopulation(data.population) + ")";
                    }
                }
            },
            scales: {
                xAxes: [{
                    id: "x",
                    type: "time",
                }],
                yAxes: [{
                    id: "y",
                    ticks: {
                        min: 0,
                        callback: function (value) {
                            return value + "%"
                        }
                    }
                }],
            },
//            annotation: {
//                drawTime: "afterDatasetsDraw",
//                annotations: [{
//                    type: "line",
//                    mode: "horizontal",
//                    display: true,
//                    scaleID: "y",
//                    value: '70',
//                    borderColor: "orange",
//                    borderWidth: 2,
//                    label: {
//                        content: "Herd immunity\u00B9",
//                        enabled: true,
//                        xAdjust: 55,
//                    }
//                }]
//            },
        },
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
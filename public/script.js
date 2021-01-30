var SUPERSCRIPT_1 = "\u00B9";
var SUPERSCRIPT_2 = "\u00B2";
var SUPERSCRIPT_3 = "\u00B3";

var DOSES = ["2_wait", "2", "1"];
var DOSE_COLORS = {
    "2_wait": "#205072",
    "2": "#56C596",
    "1": "#CFF4D2",
};
var DOSE_LABELS = {
    "2_wait": "2nd dose + 7d" + SUPERSCRIPT_1,
    "2": "2nd dose",
    "1": "1st dose",
};

function start() {
    d3.csv("latest.csv").then(initializeBarCharts);
    d3.csv("line.csv").then(initializeLineCharts);
}

function initializeBarCharts(csv) {
    makeBarChart(
        "bar-all",
        "Percent of UK vaccinated",
        csv.filter(function (row) { return row.group == "all"; }),
        makeAnnotation("vertical", "x"));
    makeBarChart(
        "bar-over-80",
        "Percent of >80s" + SUPERSCRIPT_3 + " vaccinated",
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

function initializeLineCharts(csv) {
    var csvNotExtrapolated = csv.filter(function (row) { return row.extrapolated == "False"; });
    makeLineChart("line", "UK vaccinated over time", csvNotExtrapolated, {});
    makeLineChart(
        "line-extrapolated",
        "Predicting UK vaccinations",
        csv,
        makeAnnotation("horizontal", "y"));
}

function makeLineChart(id, title, csv, annotation) {
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

    var chart = new Chart(id, {
        type: "line",
        data: {
            labels: dates,
            datasets: datasets,
        },
        options: {
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
            annotation: annotation,
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

function makeAnnotation(mode, scaleId) {
    return {
        drawTime: "afterDatasetsDraw",
        annotations: [{
            mode: mode,
            scaleID: scaleId,
            type: "line",
            display: true,
            value: '70',
            borderColor: "#FFD700",
            borderWidth: 2,
            label: {
                content: "Herd immunity" + SUPERSCRIPT_2,
                enabled: true,
                xAdjust: 55,
            }
        }]
    };
}

window.addEventListener("load", start);
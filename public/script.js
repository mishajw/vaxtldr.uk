var SUPERSCRIPT_1 = "\u00B9";
var SUPERSCRIPT_2 = "\u00B2";
var SUPERSCRIPT_3 = "\u00B3";
var SUPERSCRIPT_4 = "\u2074";

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
var GROUPS = ["<59", "60-64", "65-69", "70-74", "75-79", ">=80"].reverse();
var GOVERNMENT_TARGET_NUM = 21_043_663;
var GOVERNMENT_TARGET_PERCENT = GOVERNMENT_TARGET_NUM / 56_286_961;

function start() {
    d3.csv("latest.csv").then(initializeBarCharts);
    d3.csv("line.csv").then(initializeLineCharts);
    setLatestData();
}

function initializeBarCharts(csv) {
    makeBarChart(
        "bar-all",
        "Percent of England vaccinated",
        csv.filter(function(row) {
            return row.group == "all";
        }),
        [
            herdImmunityAnnotation("vertical", "x", true),
            governmentTargetAnnotation("vertical", "x", true),
        ],
        false /* showGroups */);
    makeBarChart(
        "bar-over-80",
        "Percent of >80s" + SUPERSCRIPT_4 + " vaccinated",
        csv,
        [],
        true /* showGroups */);
}

function makeBarChart(id, title, csv, annotations, showGroups) {
    var vaccinated_per_dose = DOSES.map(function(dose) {
        // TODO: Unnest function.
        var vaccinated = csv
            .filter(function(row) {
                if (showGroups && GROUPS.indexOf(row.group) === -1) {
                    return false;
                }
                if (!showGroups && row.group !== "all") {
                    return false;
                }
                return row.dose == dose;
            })
            .map(function(row) {
                var vaccinated = parseInt(row.vaccinated);
                var population = parseFloat(row.population);
                return {
                    x: (vaccinated / population) * 100,
                    vaccinated: vaccinated,
                    population: population,
                    group: row.group,
                };
            })
            .sort(function(v1, v2) {
                return GROUPS.indexOf(v1.group) - GROUPS.indexOf(v2.group);
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
            labels: showGroups ? GROUPS : [title],
            datasets: vaccinated_per_dose,
        },
        options: {
            tooltips: {
                callbacks: {
                    label: function(tooltipItem, data) {
                        var dataset = data.datasets[tooltipItem.datasetIndex]
                        var data = dataset.data[tooltipItem.index];
                        return dataset.label + ": " +
                            data.x.toFixed(2) + "%" +
                            " (" + formatPopulation(data.vaccinated) +
                            " of " + formatPopulation(data.population) + ")";
                    }
                }
            },
            scales: {
                yAxes: [{
                    stacked: true,
                    ticks: {
                        display: showGroups,
                    }
                }],
                xAxes: [{
                    id: 'x',
                    stacked: false,
                    ticks: {
                        min: 0,
                        max: 100,
                        callback: function(value) {
                            return value + "%"
                        }
                    }
                }],
            },
            annotation: {
                drawTime: "afterDatasetsDraw",
                annotations: annotations,
            },
        }
    });
}

function initializeLineCharts(csv) {
    var herdImmunityDate = '';
    csv.forEach(function(row) {
        if (herdImmunityDate != '' || row.dose != "2_wait") {
            return;
        }
        var vaccinated = parseInt(row.vaccinated);
        var population = parseFloat(row.population);
        if ((vaccinated / population) > 0.7) {
            herdImmunityDate = row.real_date;
        }
    });

    var csvNotExtrapolated = csv.filter(function(row) {
        return row.extrapolated == "False";
    });
    makeLineChart(
        "line",
        "England vaccinated over time",
        csvNotExtrapolated,
        [
            governmentTargetAnnotation("horizontal", "y", true),
            {
                mode: "vertical",
                scaleID: "x",
                type: "line",
                display: true,
                value: '2021-04-15',
                borderColor: "#D5212E",
                borderWidth: 2,
            }
        ],
        true);
    makeLineChart(
        "line-extrapolated",
        "Predicting England vaccinations",
        csv,
        [
            herdImmunityAnnotation("horizontal", "y", false),
            {
                mode: "vertical",
                scaleID: "x",
                type: "line",
                display: true,
                value: herdImmunityDate,
                borderColor: "#FFD700",
                borderWidth: 2,
                label: {
                    content: 'Est. ' + new Date(herdImmunityDate).toLocaleDateString(),
                    enabled: true,
                    xAdjust: 50,
                }
            }
        ]);
}

function makeLineChart(id, title, csv, annotations, limit) {
    var dates = csv
        .map(function(row) {
            return row.real_date;
        })
        .filter(distinct);
    var datasets = DOSES.map(function(dose) {
        var vaccinated = csv
            .filter(function(row) {
                return row.dose == dose;
            })
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
                        return dataset.label + ": " +
                            data.y.toFixed(2) + "%" +
                            " (" + formatPopulation(data.vaccinated) +
                            " of " + formatPopulation(data.population) + ")";
                    }
                }
            },
            scales: {
                xAxes: [{
                    id: "x",
                    type: "time",
                    time: {
                        max: limit ? '2021-04-20' : undefined,
                    }
                }],
                yAxes: [{
                    id: "y",
                    ticks: {
                        min: 0,
                        callback: function(value) {
                            return value + "%"
                        }
                    }
                }],
            },
            annotation: {
                drawTime: "afterDatasetsDraw",
                annotations: annotations,
            },
        },
    });
}

function setLatestData() {
    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function() {
        if (this.readyState != 4 || this.status != 200) {
            return;
        }
        var split = xhttp.responseText.split(" ");
        var runDate = new Date(split[0]);
        var dataDate = new Date(split[1]);
        document.getElementById("freshness").innerHTML =
            "Last updated on " + runDate.toLocaleDateString('en-GB') + ", " +
            " with data from " + dataDate.toLocaleDateString('en-GB') + ".";
    };
    xhttp.open("GET", "freshness.txt", true);
    xhttp.send();
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

function herdImmunityAnnotation(mode, scaleId, adjust) {
    return {
        mode: mode,
        scaleID: scaleId,
        type: "line",
        display: true,
        value: '70',
        borderColor: "#FFD700",
        borderWidth: 2,
        label: {
            content: "Herd immunity" + SUPERSCRIPT_3,
            enabled: true,
            xAdjust: adjust ? 55 : 0,
        }
    };
}

function governmentTargetAnnotation(mode, scaleId, adjust) {
    return {
        mode: mode,
        scaleID: scaleId,
        type: "line",
        display: true,
        value: GOVERNMENT_TARGET_PERCENT * 100,
        borderColor: "#D5212E",
        borderWidth: 2,
        label: {
            content: "April 15th target" + SUPERSCRIPT_2,
            enabled: true,
            xAdjust: adjust ? 53 : 0,
        }
    };
}

window.addEventListener("load", start);

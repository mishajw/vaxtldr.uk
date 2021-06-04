const SUPERSCRIPT_1 = "\u00B9";
const SUPERSCRIPT_2 = "\u00B2";
const SUPERSCRIPT_3 = "\u00B3";
const SUPERSCRIPT_4 = "\u2074";

const DOSES = ["2_wait", "2", "1"];
const DOSE_COLORS = {
    "2_wait": "#205072",
    "2": "#56C596",
    "1": "#CFF4D2",
};
const DOSE_LABELS = {
    "2_wait": "Dose 2 +7d" + SUPERSCRIPT_1,
    "2": "Dose 2",
    "1": "Dose 1",
};
const GROUPS = ["<=29", "30-34", "35-39", "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", "75-79", ">=80"].reverse();
// Source: Table 2 on https://www.gov.uk/government/publications/uk-covid-19-vaccines-delivery-plan/uk-covid-19-vaccines-delivery-plan
const GOVERNMENT_TARGET_NUM = 44_000_000;
const GOVERNMENT_TARGET_PERCENT = GOVERNMENT_TARGET_NUM / 56_286_961;

async function start() {
    initializeLineCharts(await getLatestDataDate());
    initializeBarCharts();
}

async function initializeBarCharts() {
    const csv = await d3.csv("latest.csv");
    makeBarChart(
        "bar-all",
        "Percent of England vaccinated",
        csv.filter(row => row.group === "all"),
        [
            herdImmunityAnnotation("vertical", "x", true),
            governmentTargetAnnotation("vertical", "x", true)
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
    const vaccinated_per_dose = DOSES.map(dose => {
        // TODO: Unnest function.
        const vaccinated = csv
            .filter(row => {
                if (showGroups && GROUPS.indexOf(row.group) === -1) {
                    return false;
                }
                if (!showGroups && row.group !== "all") {
                    return false;
                }
                return row.dose === dose;
            })
            .map(row => {
                const vaccinated = parseInt(row.vaccinated);
                const population = parseFloat(row.population);
                return {
                    x: (vaccinated / population) * 100,
                    vaccinated: vaccinated,
                    population: population,
                    group: row.group
                };
            })
            .sort((v1, v2) => GROUPS.indexOf(v1.group) - GROUPS.indexOf(v2.group));
        return {
            label: DOSE_LABELS[dose],
            backgroundColor: DOSE_COLORS[dose],
            data: vaccinated
        };
    });
    new Chart(id, {
        type: "horizontalBar",
        data: {
            labels: showGroups ? GROUPS : [title],
            datasets: vaccinated_per_dose
        },
        options: {
            tooltips: {
                callbacks: {
                    label: (tooltipItem, data) => {
                        const dataset = data.datasets[tooltipItem.datasetIndex];
                        const datasetData = dataset.data[tooltipItem.index];
                        return dataset.label + ": " +
                            datasetData.x.toFixed(2) + "%" +
                            " (" + formatPopulation(datasetData.vaccinated) +
                            " of " + formatPopulation(datasetData.population) + ")";
                    }
                }
            },
            scales: {
                yAxes: [{
                    stacked: true,
                    ticks: {
                        display: showGroups
                    }
                }],
                xAxes: [{
                    id: "x",
                    stacked: false,
                    ticks: {
                        min: 0,
                        max: 100,
                        callback: value => value + "%"
                    }
                }]
            },
            annotation: {
                drawTime: "afterDatasetsDraw",
                annotations: annotations
            }
        }
    });
}

async function initializeLineCharts(latestDataDate) {
    const csv = await d3.csv("line.csv")
    const herdImmunityDate = csv.find(row => {
        if (row.dose !== "2_wait") {
            return false;
        }
        const vaccinated = parseInt(row.vaccinated);
        const population = parseFloat(row.population);
        return (vaccinated / population) > 0.7;
    }).real_date;

    const csvNotExtrapolated = csv.filter(row => row.extrapolated === "False");
    makeLineChart(
        "line",
        csvNotExtrapolated,
        [
            governmentTargetAnnotation("horizontal", "y", false),
            {
                mode: "vertical",
                scaleID: "x",
                type: "line",
                display: true,
                value: "2021-07-31",
                borderColor: "#D5212E",
                borderWidth: 2
            }
        ],
        true);
    makeLineChart(
        "line-extrapolated",
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
                    content: "Est. " + new Date(herdImmunityDate).toLocaleDateString(),
                    enabled: true
                }
            },
            {
                mode: "vertical",
                scaleID: "x",
                type: "line",
                display: true,
                value: latestDataDate,
                borderColor: "#03a5fc",
                borderWidth: 2,
                label: {
                    content: "Latest data, " + new Date(latestDataDate).toLocaleDateString(),
                    enabled: true
                }
            }
        ]);
}

function makeLineChart(id, csv, annotations, limit) {
    const dates = csv
        .map(row => row.real_date)
        .filter(distinct);
    const datasets = DOSES.map(dose => {
        const vaccinated = csv
            .filter(row => row.dose === dose)
            .map(row => {
                const vaccinated = parseInt(row.vaccinated);
                const population = parseFloat(row.population);
                return {
                    x: row.real_date,
                    y: (vaccinated / population) * 100,
                    vaccinated: vaccinated,
                    population: population
                };
            });
        return {
            label: DOSE_LABELS[dose],
            backgroundColor: DOSE_COLORS[dose],
            data: vaccinated
        };
    });

    new Chart(id, {
        type: "line",
        data: {
            labels: dates,
            datasets: datasets
        },
        options: {
            tooltips: {
                callbacks: {
                    label: (tooltipItem, data) => {
                        const dataset = data.datasets[tooltipItem.datasetIndex];
                        const datasetData = dataset.data[tooltipItem.index];
                        return dataset.label + ": " +
                            datasetData.y.toFixed(2) + "%" +
                            " (" + formatPopulation(datasetData.vaccinated) +
                            " of " + formatPopulation(datasetData.population) + ")";
                    }
                }
            },
            scales: {
                xAxes: [{
                    id: "x",
                    type: "time",
                    time: {
                        max: limit ? "2021-08-10" : undefined
                    }
                }],
                yAxes: [{
                    id: "y",
                    ticks: {
                        min: 0,
                        callback: value => value + "%"
                    }
                }]
            },
            annotation: {
                drawTime: "afterDatasetsDraw",
                annotations: annotations
            }
        }
    });
}

/**
 * @returns Promise<Date>
 */
async function getLatestDataDate() {
    const response = await fetch("freshness.txt");
    const text = await response.text();
    const [runDate, dataDate] = text
        .split(" ")
        .map(dateStr => new Date(dateStr));
    document.getElementById("freshness").innerHTML =
        "Last updated on " + runDate.toLocaleDateString("en-GB") + ", " +
        " with data from " + dataDate.toLocaleDateString("en-GB") + ".";
    return dataDate;
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
        value: "70",
        borderColor: "#FFD700",
        borderWidth: 2,
        label: {
            content: "Herd immunity" + SUPERSCRIPT_3 + " (dose 2 +7d)",
            enabled: true,
            yAdjust: adjust ? -20 : 0
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
            content: "July target" + SUPERSCRIPT_2 + " (dose 1)",
            enabled: true,
            yAdjust: adjust ? 20 : 0
        }
    };
}

window.addEventListener("load", start);

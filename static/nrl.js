var team_col = {
    'Brisbane Broncos': '#680032',
    'Canberra Raiders': '#B4D224',
    'Canterbury Bulldogs': '#074094',
    'Cronulla Sharks': '#0F7BB8',
    'Gold Coast Titans': '#F9A132',
    'Manly Sea Eagles': '#680032',
    'Melbourne Storm': '#641379',
    'New Zealand Warriors': '#96989C',
    'Newcastle Knights': '#074094',
    'North QLD Cowboys': '#FED908',
    'Parramatta Eels': '#FECB0A',
    'Penrith Panthers': '#0C5D6F',
    'South Sydney Rabbitohs': '#186935',
    'St George Dragons': '#E6151C',
    'Sydney Roosters': '#053368',
    'Wests Tigers': '#F48521'
}

var margin = {top: 30, right: 20, bottom: 40, left: 50},
width = 900 - margin.left - margin.right,
height = 600 - margin.top - margin.bottom;

var x = d3.scaleLinear().range([0,width]);
var y = d3.scaleLinear().range([height,0]);

var xAxis = d3.axisBottom(x);

var yAxis = d3.axisLeft(y).tickValues([]);

var valueline = d3.line()
    .x(function(d) { return x(d.round); })
    .y(function(d) { return y(d.form); })
    .curve(d3.curveCardinal);

var div = d3.select("body").append("div")
    .attr("class", "tooltip")
    .style("opacity", 0);

    var svg = d3.select("#chartArea")
        .attr(
          "style",
          "padding-bottom: " + Math.ceil(height * 100 / width) + "%"
        )
        .append("svg")
        .attr("viewBox", "0 0 " + (width+margin.left+margin.right) + " " + (height+margin.top+margin.bottom))
            .style("background-color", "#C5C5C5")
            .style("border-radius", "12px")
        .append("g")
            .attr("transform",
                  "translate(" + margin.left + "," + margin.top + ")");

    d3.json("https://nrlform.appspot.com/v1/nrlform").then(function(data) {
        data = data.filter(function(d) {
            return d.year == 2019;
        });
        data.forEach(function(d) {
            d.round = +d.round;
            d.form = +d.form;
        });
        x.domain(d3.extent(data, function(d) { return d.round}))
        y.domain([d3.min(data, function(d) {return d.form}), d3.max(data, function(d) {return d.form})])

        var dataNest = d3.nest()
            .key(function(d) { return d.team;})
            .entries(data);

        dataNest.forEach(function(d, i) {
            svg.append("path")
                .attr("class", "line")
                .attr("id", 'tag'+d.key.replace(/\s+/g, ''))
                .attr("d", valueline(d.values))
                .style("stroke", team_col[d.values[0].team])
                .on("mouseover", function() {
                    d3.selectAll(".line")
                        .style("opacity", 0.3)
                        .style("stroke-width", 2);
                    d3.select("#tag"+d.key.replace(/\s+/g, ''))
                        .style("stroke-width", 5)
                        .style("opacity", 1);
                    div.style("opacity", .9);
                    div.html(d.values[0].team)
                        .style("left", (d3.event.pageX) + "px")
                        .style("top", (d3.event.pageY - 28) + "px");
                })
                .on("mouseout", function(d) {
                    div.transition()
                        .duration(300)
                        .style("opacity", 0);
                    d3.selectAll(".line")
                        .style("opacity", 1)
                        .style("stroke-width", 3);
                });
        });

		svg.append("g")
            .attr("class", "xaxis")
            .attr("transform", "translate(0," + height + ")")
            .call(xAxis);

        svg.append("text")
            .attr("transform",
                    "translate(" + (width/2) + " ," +
                                   (height + margin.top) + ")")
            .style("text-anchor", "middle")
            .text("Round");

        svg.append("g")
            .attr("class", "yaxis")
            .call(yAxis);

        svg.append("text")
            .attr("transform", "rotate(-90)")
            .attr("y", 0 - (margin.left / 2))
            .attr("x",0 - (height / 2))
            .attr("dy", "1em")
            .style("text-anchor", "middle")
            .text("Form");
    });

function updateGraph(year) {

d3.json("https://nrlform.appspot.com/v1/nrlform").then(function(data) {
    data = data.filter(function(d) {
        return d.year == year;
    });
    data.forEach(function(d) {
        d.round = +d.round;
        d.form = +d.form;
    });
    x.domain(d3.extent(data, function(d) { return d.round}))
    y.domain([d3.min(data, function(d) {return d.form}), d3.max(data, function(d) {return d.form})])

    var dataNest = d3.nest()
        .key(function(d) { return d.team;})
        .entries(data);

    var svg = d3.select("#chartArea").transition();

    dataNest.forEach(function(d, i) {
        svg.select("#"+'tag'+d.key.replace(/\s+/g, ''))
            .duration(750)
            .attr("d", valueline(d.values))
            });

        svg.select(".xaxis")
            .transition(500)
            .call(xAxis);

        svg.select(".yaxis")
            .transition(500)
            .call(yAxis)
            .selectAll("text")
            .remove();
    });
};

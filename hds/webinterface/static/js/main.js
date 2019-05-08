// Get stats about the node

const pStats = fetch(new Request('../webinterface/stats')).then((response) => {
  return response.json();
})
const pTopics = fetch(new Request('../_hds/topics')).then((response) => {
  return response.json();
})

Promise.all([pStats, pTopics]).then((val) => {
    return createGraph(val[0], val[1].topics);
}).catch((err) => {
    console.error("Failed to get all the stuff I needed to start", err);
});

async function createGraph(stats, topics) {

    document.querySelector("#instance_name").innerHTML = stats.name;

    const drag = (simulation) => {

      function dragstarted(d) {
        if (!d3.event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      }

      function dragged(d) {
        d.fx = d3.event.x;
        d.fy = d3.event.y;
      }

      function dragended(d) {
        if (!d3.event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      }

      return d3.drag()
          .on("start", dragstarted)
          .on("drag", dragged)
          .on("end", dragended);
    }

    console.log("Creating a graph for", stats, topics);
    const width = 1024, height = 1024;
    const topic_color = "#22BB22";
    const host_color = "#EE2111";
    const server_color = "#2244BB";
    const localhost = stats.servername.substr(0, 64);

    let nodes = [
        {id: localhost, full_id: stats.servername, group: 1, color: host_color, isTopic: false},
    ];

    nodes = nodes.concat(topics.map(t =>
        ({id: `topic_${t}`, color: topic_color, isTopic: true})
    ));

    const links = topics.map((t) =>
        ({"source": localhost, "target": `topic_${t}`, "weight": 1})
    );

    // Get subtopics
    await Promise.all(topics.map(async (t) =>  {
       const topicRes = await fetch(new Request(`../_hds/topics/${t}`)).then((response) => response.json());
       const hosts = Object.keys(topicRes.hosts); // Hosts
       hosts.forEach((h) => {
            if (!nodes.find((host) => host.full_id === h)) {
                nodes.push({
                   id: h.substr(0, 64),
                   full_id: h,
                   group: 1,
                   color: server_color,
                   isTopic: false
                });
            }

            console.log(nodes);

            links.push({
                source: h.substr(0, 64),
                target: `topic_${t}`,
                weight: 1,
            });
       });
       hosts.forEach((h) => {
           //topicRes[h].subtopics
       });
       console.log(topicRes);

    }));

    const simulation = d3.forceSimulation(nodes)
        .force("link", d3.forceLink(links).id(d => d.id).distance(100))
        .force("charge", d3.forceManyBody())
        .force("center", d3.forceCenter(width / 2, height / 2));

    const svg = d3.select("section#map").append("svg")
        .attr("width", width)
        .attr("height", height);

    const link = svg.append("g")
        .attr("stroke", "#999")
        .attr("stroke-opacity", 0.6)
        .selectAll("line")
        .data(links)
        //.distance(50)
        .enter().append("line")
        .attr("stroke-width", d => 3);

      const node = svg.append("g")
          .attr("stroke", "#000000")
          .attr("stroke-width", 1.5)
          .selectAll("circle")
          .data(nodes)
          .enter().append("circle")
          .attr("r", 15)
          .attr("fill", (d) => d.color)
           .call(drag(simulation));

    node.append("title")
      .text(d => d.id);

    simulation.on("tick", () => {
        link
            .attr("x1", d => d.source.x)
            .attr("y1", d => d.source.y)
            .attr("x2", d => d.target.x)
            .attr("y2", d => d.target.y);

        node
            .attr("cx", d => d.x)
            .attr("cy", d => d.y);
    });

    document.querySelector("svg").onclick = async (ev) => {
        const node = nodes.find((e) => e.id === ev.target.textContent);
        if (!node) { return };
        const name = node.isTopic ? node.id.substr("topic_".length) : node.id;
        if (!node.isTopic) {
            // Get state
            const state = await fetch(new Request(`../_hds/hosts/${node.full_id}`)).then((response) => response.json());
            console.log(state);
        }
        document.querySelector("section#stats > #node_name").innerHTML = name;
    };

    //invalidation.then(() => force.stop());

    // force.nodes(nodes)
    //   .links(links)
    //   .start();
}
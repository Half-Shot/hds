class Viewer {
    constructor (uiHandler) {
        this.uiHandler = uiHandler;
    }

    connectToHost(location) {
        console.log("Connecting to", location);

        if (!location.includes(":")) {
            location += ":27012";
        }

        return fetch(`https://${location}/_hds/identify`).then((res) => {
            console.log("Connected to host");
            return res.json();
        }).then((identity) => {
            this.location = location;
            this.serverName = identity["hds.servername"];
            this.getState(this.serverName).then((state) => {
                this.uiHandler.setName(state["hds.name"].value);
                if (state["hds.contact.name"]) {
                    this.uiHandler.setContactDetails(state["hds.contact.name"].value, state["hds.contact.email"].value)
                }
            });
            this.uiHandler.setServerName(this.serverName.substr(0, 64) + "...");
            this.uiHandler.setState("connected");
            if (identity["hds.type"] != "hds.directory") {
                throw Error("Not a directory server");
            }
        }).catch((ex) => {
            this.uiHandler.setState("connection-failed", ex);
            console.error("Failed to connect to hds instance:", ex);
            throw ex;
        });
    }

    getState(serverName) {
        return fetch(`https://${this.location}/_hds/hosts/${serverName}`).then((res) => {
            console.log("Getting state for", serverName);
            return res.json();
        }).catch((ex) => {
            console.error("Failed to get state:", ex);
        });
    }

    getTopics() {
        return fetch(`https://${this.location}/_hds/topics`).then((res) => {
            return res.json();
        }).then((res) => res.topics).catch((ex) => {
            console.error("Failed to get topics:", ex);
        });
    }

    storeDefaultHDSService(host, serverName) {
        localStorage.setItem("hds.host", this.location);
        localStorage.setItem("hds.servername", this.serverName);
    }
}

class UiHandler {
    constructor(onSearch) {
        this.panel = {};
        this.panel.connecting = document.querySelector("#connecting");
        this.panel.connectionFailed = document.querySelector("#connectionFailed");
        this.panel.connectionFailedReason = document.querySelector("#connectionFailed #reason");
        this.panel.hostConsole = document.querySelector("#hostConsole");
        this.search = document.querySelector("#topicSearch");
        this.searchTimeout = null;
        this.search.onkeydown = (e) => {
            // Hack to check that this is a text key press.
            if (e.key.length > 1 && this.search.value.length != 0) { return; }
            clearTimeout(this.searchTimeout);
            this.searchTimeout = setTimeout(onSearch.bind(null, this.search.value), 500);
        };
    }

    setServerName(name) {
        document.querySelector("#hostname").innerHTML = name;
    }

    setName(name) {
        document.querySelector("#friendly-name").innerHTML = name;
    }

    setContactDetails(name, email) {
        const contact = document.querySelector("#contactName");
        contact.innerHTML = name;
        if (email) {
            contact.href = `mailto:${email}`;
        }
    }

    setSearchTopics(topics, searchText=null) {
        document.querySelector("#searchResultsText").hidden = !searchText;
        document.querySelector("#searchResultsText #searchTerm").innerHTML = searchText;
        document.querySelector("#topicSearchResult tbody").innerHTML = topics.map((topic) => {
            let count = 0;
            return `<tr><td>${topic}</td><td>${count}</td></tr>`;
        }).join("\n");
    }

    setState(state, args) {
        console.debug("Changed state to", state);
        if (state === "connected") {
            this.panel.hostConsole.hidden = false;
            this.panel.connecting.hidden = true;
            this.panel.connectionFailed.classList.add("hidden");
            this.search.disabled = false;
        } else if (state === "connection-failed") {
            this.panel.connecting.hidden = true;
            uiHandler.panel.connectionFailed.classList.remove("hidden");
            this.panel.connectionFailedReason.innerHTML = args;
        }
    }
}

async function onSearch(searchText) {
    console.log("Searching for", `"${searchText}"`);
    let topics = await window.xhdsViewer.getTopics();
    if (searchText) {
        topics = topics.filter((s) => s.includes(searchText));
    }
    window.uiHandler.setSearchTopics(topics, searchText);
}

function main() {
    window.uiHandler = new UiHandler(onSearch);
    window.xhdsViewer = new Viewer(window.uiHandler);
    window.xhdsViewer.connectToHost(
        decodeURIComponent(window.location.hash.substr("#!/ext%2Bhds%3A".length))
    ).then(() => onSearch());
    document.querySelector("#setDefaultButton").onclick = () => {
        window.xhdsViewer.storeDefaultHDSService();
    };
}


// hds-host

// Get topics

// Get subtopics

document.body.onload = main;

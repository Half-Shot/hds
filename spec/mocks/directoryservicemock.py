class MockResponse():

    def __init__(self, status=200, json=None):
        self.status = status
        self.__json = json

    async def json(self):
        return self.__json

class MockClientSession():
    def __init__(self, opts, state={}):
        self.requests = []
        self.topics = opts.get("topics", {})
        self.all_topics = opts.get("all_topics", [])
        self.state = state
        pass

    async def store_method(self, method, url=None, json=None):
        if url is None:
            raise Exception("URL expected")
        if json is None and method != "GET":
            raise Exception("JSON expected")
        self.requests.append({
            "url": url,
            "json": json,
            "method": method,
        })

    async def put(self, url=None, json=None, ssl=None):
        await self.store_method("PUT", url, json)
        return MockResponse(201)

    async def get(self, url=None, ssl=None):
        await self.store_method("GET", url)
        parts = url.split("/")
        req_type = parts[4]
        if req_type == "topics" and len(parts) > 5:
            topic = "/".join(parts[5:]) # Include subtopics
            # This is a topic request.
            hosts = self.topics.get(topic, [])
            if len(hosts) == 0:
                return MockResponse(404, {
                    "hds.error.text": "Topic could not be found",
                    "hds.error": "hds.error.topic.missing",
                })
            return MockResponse(200, {"hosts": hosts})
        elif req_type == "topics":
            return MockResponse(200, {"topics": self.all_topics})
        elif req_type == "hosts" and len(parts) == 6:
            srv = parts[5]
            s = self.state.get(srv)
            if s is None:
                return MockResponse(404, {
                    "hds.error.text": "Host could not be found",
                    "hds.error": "hds.error.host.missing",
                })
            return MockResponse(200, s)
        elif req_type == "identify":
            return MockResponse(200, {
                "hds.servername": "a_server_name",
                "hds.type": "hds.directory"
            })
        raise Exception("Mock client didn't understand the request")

    async def __aexit__(self, exc_type, exc, tb):
        return len(self.requests) > 0

    async def __aenter__(self):
        return self
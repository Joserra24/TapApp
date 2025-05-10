from locust import HttpUser, TaskSet, task, between

class UserBehavior(TaskSet):
    def on_start(self):
        self.client.post("/login/", data={"username":"tester","password":"test1234"})

    @task(3)
    def view_index(self):
        self.client.get("/")

    @task(2)
    def list_pedidos(self):
        self.client.get("/pedidos/")

    @task(1)
    def crear_pedido(self):
        payload = {
            "mesa": "10", "numero_clientes": 2,
            "productos": [1,2], "cantidades": '{"1":1,"2":2}'
        }
        self.client.post("/crear_pedido/", data=payload)

class WebsiteUser(HttpUser):
    tasks = [UserBehavior]
    wait_time = between(1, 3)

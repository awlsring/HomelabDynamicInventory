from typing import List, Dict
from pymongo import MongoClient
from ansible.plugins.inventory import BaseInventoryPlugin
from ansible.plugins.inventory import Cacheable
from ansible.plugins.inventory import Constructable
from ansible.inventory.data import InventoryData


class Machine:
    def __init__(self, machine: dict) -> None:
        self.id: str = machine["_id"]
        self.name: str = machine["name"]
        self.ip: str = machine["ip"]
        self.mac: str = machine["mac"]
        self.network: str = machine["network"]
        self.modules: List[str] = machine["modules"]
        self.tags: List[Dict[str, str]] = machine["tags"]


class HomelabDBClient:
    def __init__(self, user, password, host, port, database) -> None:
        connection = f"mongodb://{user}:{password}@{host}:{port}/{database}"
        self.mongo = MongoClient(connection)
        self.database = self.mongo.get_database(database)
        self.machine_collection = self.database.get_collection("machines")

    def get_all(self) -> List[Machine]:
        machines: List[Machine] = []
        all = self.machine_collection.find()
        for machine in all:
            machines.append(Machine(machine))
        return machines

    def get_group(self, group_name) -> List[Machine]:
        machines: List[Machine] = []
        group = self.machine_collection.find({"tags": {"group": group_name}})
        for machine in group:
            machines.append(Machine(machine))
        return machines


DOCUMENTATION = r'''
    name: HomelabDynamicInventory
    plugin_type: inventory
    short_description: Returns Ansible inventory from HomelabDB
    description: Returns Ansible inventory from HomelabDB
    options:
      plugin:
          description: Name of the plugin
          required: true
          choices: ['homelab_inventory']
      user:
        destription: User to acces local database with
        required: true
      password:
        description: Password to acces local database
        required: true
      host:
        description: Host to connect to
        required: true
      port:
        description: Port MongoDB is running on
        required: true
      database:
        description: Database to connect to.
        required: true
      target_group:
        description: Target group to get.
        required: false
'''


class InventoryModule(BaseInventoryPlugin, Constructable, Cacheable):
    NAME = 'homelab_inventory'

    def verify_file(self, path):
        super(InventoryModule, self).verify_file(path)
        if path.endswith((".yaml", ".yml")):
            return True
        return False

    def parse(self, inventory, loader, path, cache=True):
        super(InventoryModule, self).parse(inventory, loader, path, cache)

        self.inventory: InventoryData = inventory
        config = self._read_config_data(path)
        self.database = HomelabDBClient(
            config["user"],
            config["password"],
            config["host"],
            config["port"],
            config["database"]
        )

        if config.get("target_group", False):
            machines = self.database.get_group(config["target_group"])
        else:
            machines = self.database.get_all()

        for machine in machines:
            self.inventory.add_host(machine.ip)
        for tag in machine.tags:
            for key, value in tag.items():
                if key == "group":
                    self.inventory.add_group(value)
                    self.inventory.add_host(machine.ip, group=value)
                else:
                    self.inventory.set_variable(machine.ip, key, value)

        print(self.inventory.__dict__)

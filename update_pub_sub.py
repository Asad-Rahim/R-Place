primary_redis_endpoint = 'redis-001.wicy8d.0001.use1.cache.amazonaws.com'
redis_port = 6379
primary_redis_client = redis.StrictRedis(host=primary_redis_endpoint, port=redis_port, decode_responses=True)

def read_config_from_file():
    with open("pub_sub.txt", 'r') as file:
        lines = file.readlines()
        for line in lines:
            key, value = line.split(" ")
            primary_redis_client.set(key, value)



if __name__ == "__main__":
    read_config_from_file()
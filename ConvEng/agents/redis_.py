import redis
import pickle

# Initialize Redis connection
r = redis.Redis(host='localhost', port=6379, db=0)

def store_agent_in_cache(key, agent):
    print("Storing In CACHE")
    """Serialize and store the LLMChain agent in Redis."""
    serialized_agent = pickle.dumps(agent)
    r.set(key, serialized_agent)

def get_agent_from_cache(key):
    print("Getting from CACHE")
    """Retrieve and deserialize the LLMChain agent from Redis."""
    serialized_agent = r.get(key)
    if serialized_agent:
        return pickle.loads(serialized_agent)
    return None

def get_agent(cache_key):
    """Retrieve agent_executor from cache or create a new one if it doesn't exist."""
    # Try to get the executor from Redis cache
    executor = get_agent_from_cache(cache_key)
    
    if executor is None:
        return None
    return executor



import asyncio 
from app.database.qdrant_database import init_qdrant, search_similar 
async def test(): 
    await init_qdrant() 
    results = await search_similar('cancer', limit=5, score_threshold=0.1) 
    print(f'Resultats: {len(results)}') 
asyncio.run(test()) 

from MediaScript import parse
import asyncio
iscript_string = """loadfile kc.mov m
contrast m -1
explode m
copy m a
copy m a2
audiopitch m 0.5
audiopitch a 1.4983070768766815
audiopitch a2 2
overlay m a
volume m
overlay m a2
volume m
audiopitch m 1.122462048309373
render m gm74"""
results = asyncio.run(parse(iscript_string,playoutput=True))
print(results)
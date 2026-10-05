const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { test } = require('node:test');
const source = fs.readFileSync(require('node:path').join(__dirname, '../web/app.js'), 'utf8');
const code = source.slice(source.indexOf('async function moveCrown('), source.indexOf('\nfunction renderCrowns('));

function context(api) {
  const state = { crowns: [{id:'a',name:'Rey-Dau',small:false,gold:false}, {id:'hidden',name:'Arkveld',small:true,gold:false}, {id:'b',name:'Rathian',small:false,gold:true}, {id:'c',name:'Chatacabra',small:true,gold:true}] };
  const status = {value:''};
  const search = {value:''};
  const notes = [];
  const sandbox = vm.createContext({state,crownStatus:status,crownSaving:false,serverOnline:true,
    api,toast:(...args)=>notes.push(args),renderCrowns(){},
    $:id=>id==='crown-search' ? search : {querySelector:()=>({focus(){}})} });
  vm.runInContext(code, sandbox);
  return {state,status,search,notes,sandbox};
}

test('each crown filter selects its exact combination and search tolerates punctuation',()=>{
  const app=context();
  for (const [status,ids] of [['none',['a']],['small',['hidden']],['gold',['b']],['complete',['c']],['',['a','hidden','b','c']]]) {
    app.status.value=status;
    const actual=vm.runInContext('state.crowns.filter(crownMatches).map(m=>m.id)',app.sandbox);
    assert.deepEqual(Array.from(actual),ids);
  }
  app.search.value='Rey Dau';
  assert.deepEqual(Array.from(vm.runInContext('state.crowns.filter(crownMatches).map(m=>m.id)',app.sandbox)),['a']);
});

test('moving a filtered monster saves the complete order and preserves hidden entries',async()=>{
  let sent;
  const app=context(async(path,body)=>{sent={path,ids:Array.from(body.ids)};});
  await vm.runInContext("moveCrown('a','b')",app.sandbox);
  assert.equal(sent.path,'/api/crowns/order');
  assert.deepEqual(sent.ids,['hidden','b','a','c']);
  assert.deepEqual(Array.from(app.state.crowns,m=>m.id),sent.ids);
});

test('a failed order save retains the last persisted display order',async()=>{
  const app=context(async()=>{throw new Error('Speichern fehlgeschlagen');});
  await vm.runInContext("moveCrown('a','c')",app.sandbox);
  assert.deepEqual(Array.from(app.state.crowns,m=>m.id),['a','hidden','b','c']);
  assert.equal(app.notes[0][0],'Speichern fehlgeschlagen');
  assert.equal(app.notes[0][1],true);
  assert.equal(vm.runInContext('crownSaving',app.sandbox),false);
});

test('dropping anywhere on a card moves to its position in either direction',async()=>{
  const renderCode=source.slice(source.indexOf('function renderCrowns('),source.indexOf("\n$('nav-quests').addEventListener"));
  for (const [from,to,expected] of [
    ['a','hidden',['hidden','a','b','c']],
    ['hidden','a',['hidden','a','b','c']],
    ['a','c',['hidden','b','c','a']],
    ['c','a',['c','a','hidden','b']],
  ]) {
    for (const [clientX,clientY] of [[10,10],[90,10],[10,50],[90,50],[10,90],[90,90]]) {
      let sent;
      const app=context(async(path,body)=>{sent=Array.from(body.ids);});
      const elements=new Map();
      const node=(attrs={},children=[])=>({...attrs,children,style:{},
        classList:{add(){},remove(){}},
        replaceChildren(...items){this.children=items;},
        querySelector(){return {focus(){}};},
        getBoundingClientRect(){return {left:0,top:0,width:100,height:100};},
      });
      Object.assign(app.sandbox,{
        crownDragging:null,
        $:id=>{
          if(id==='crown-search')return app.search;
          if(!elements.has(id))elements.set(id,node());
          return elements.get(id);
        },
        el:(tag,attrs,children)=>node(attrs,children),
        icon(){},monsterGlyph(){},updateConnectionControls(){},
      });
      vm.runInContext(renderCode+'\nrenderCrowns();',app.sandbox);
      const cards=elements.get('crown-list').children;
      const sourceCard=cards.find(card=>card['data-monster-id']===from);
      const targetCard=cards.find(card=>card['data-monster-id']===to);
      sourceCard.children[0].children[0].ondragstart({dataTransfer:{setData(){}}});
      await targetCard.ondrop({clientX,clientY,preventDefault(){}});
      await new Promise(resolve=>setImmediate(resolve));
      assert.deepEqual(sent,expected,`${from} → ${to} at ${clientX},${clientY}`);
      assert.deepEqual(Array.from(app.state.crowns,m=>m.id),expected);
      assert.equal(app.sandbox.crownDragging,null);
    }
  }
});

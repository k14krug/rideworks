/* Playwright CLI run-code against an explicitly supplied disposable synthetic server. */
async page => {
  const base='http://127.0.0.1:8777';
  let checks=0;const cases=[];
  const check=(v,m)=>{checks++;if(!v)throw new Error(m);};
  const browser=page.context().browser();
  for(const javaScriptEnabled of [true,false])for(const timezoneId of ['UTC','Asia/Tokyo']) {
    const context=await browser.newContext({javaScriptEnabled,timezoneId});
    const tab=await context.newPage();const errors=[];
    tab.on('pageerror',e=>errors.push(e.message));
    let navigations=0;tab.on('request',r=>{if(r.isNavigationRequest()&&r.frame()===tab.mainFrame())navigations++;});
    await tab.goto(base);await tab.waitForLoadState('networkidle');
    check(navigations===1,'Home must render without JS navigation');
    for(const [name,path,content] of [['Home','/','Mileage Progress'],['Plan','/plan','Daily rotation'],
                                    ['Training State','/training-state','Training State'],['Activities','/activities','Title search'],
                                    ['Settings','/settings','Annual cycling mileage goal'],['Performance','/performance','20-minute']]) {
      if(path!=='/')await tab.getByRole('navigation',{name:'Main'}).getByRole('link',{name,exact:true}).click();
      await tab.waitForLoadState('networkidle');
      check(new URL(tab.url()).pathname===path,'ordinary link destination');
      check(new URL(tab.url()).search==='','ordinary links stay ordinary');
      check(await tab.locator('html').getAttribute('data-display-timezone')==='America/Los_Angeles','LA default independent of browser');
      check((await tab.locator('main').textContent()).includes(content),'substantive first response '+path);
      check(!((await tab.locator('main').textContent()).includes('Enable JavaScript to use')),'no calendar fallback');
      if(path==='/activities')check(await tab.locator('input[name=tz]').inputValue()==='America/Los_Angeles','filter keeps server zone');
      if(path==='/plan'||path==='/settings')check(await tab.locator('input[name=tz]').first().inputValue()==='America/Los_Angeles','form uses server zone');
      if(javaScriptEnabled)for(const time of await tab.locator('[data-local-time]').all())check(await time.getAttribute('data-timezone')==='America/Los_Angeles','date labels use server zone');
    }
    check(navigations===6,'exactly one navigation per ordinary page');
    if(javaScriptEnabled) {
      await tab.goto(base+'/plan');await tab.waitForLoadState('networkidle');const before=navigations;
      await tab.evaluate(()=>window.dispatchEvent(new Event('focus')));await tab.waitForLoadState('networkidle');
      check(navigations===before,'Plan focus refresh uses server calendar');
    }
    for(const zone of ['UTC','Asia/Tokyo'])for(const [path,key] of [['/','home_tz'],['/plan','plan_tz'],['/training-state','tz'],['/activities','tz'],['/settings','tz'],['/performance','curve_tz']]) {
      const target=base+path+'?'+new URLSearchParams({[key]:zone});const before=navigations;
      const response=await tab.goto(target);await tab.waitForLoadState('networkidle');
      check(response.status()===200,'valid explicit zone');check(tab.url()===target,'explicit bookmark preserved');
      check(navigations===before+1,'no explicit-zone redirect');
      check(await tab.locator('html').getAttribute('data-display-timezone')===(key==='curve_tz'?'America/Los_Angeles':zone),'explicit display zone');
      if(key==='curve_tz')check(JSON.parse(await tab.locator('#power-curve-data').textContent()).calendar_timezone===zone,'explicit curve calendar');
      if(javaScriptEnabled)for(const time of await tab.locator('[data-local-time]').all())check(await time.getAttribute('data-timezone')===(key==='curve_tz'?'America/Los_Angeles':zone),'explicit date display preserved');
    }
    for(const [path,key] of [['/','home_tz'],['/plan','plan_tz'],['/training-state','tz'],['/activities','tz'],['/settings','tz'],['/performance','curve_tz']]) {
      const before=navigations;const response=await tab.goto(base+path+'?'+key+'=bad');await tab.waitForLoadState('networkidle');
      check(response.status()===400,'invalid explicit zone rejected');check(navigations===before+1,'invalid zone no loop');
      check((await tab.locator('h1').textContent())==='Invalid timezone','transparent invalid-zone explanation');
    }
    check(errors.length===0,'no browser errors '+JSON.stringify(errors));cases.push({javaScriptEnabled,timezoneId,navigations});await context.close();
  }
  return {checks,cases};
}

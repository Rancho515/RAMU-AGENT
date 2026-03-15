function scheduleCall(){

fetch("/schedule_call",{
method:"POST",
headers:{"Content-Type":"application/json"},
body:JSON.stringify({
phone:document.getElementById("phone").value,
time:document.getElementById("time").value
})
})
.then(res=>res.json())
.then(()=>loadCalls())

}

function loadCalls(){

fetch("/calls")
.then(res=>res.json())
.then(data=>{

let body=""

data.forEach(c=>{

body+=`

<tr>
<td>${c.phone}</td>
<td>${c.time}</td>
<td class="status-${c.status}">${c.status}</td>
<td>${c.message}</td>
</tr>
`

})

document.getElementById("callBody").innerHTML=body

})

}

setInterval(loadCalls,2000)

loadCalls()

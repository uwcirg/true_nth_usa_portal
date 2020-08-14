export function getWrapperJS (el) {
    if (!el) return;
    let jsSet = document.querySelectorAll(`${el} script`); 
    jsSet.forEach(item => {
        var d=document, g=d.createElement("script"), b=d.getElementsByTagName("body")[0];
        if (!item.getAttribute("src")) {
            g.innerHTML = item.innerHTML;
            b.appendChild(g);
            return true;
        }
        let props = {
            type: "text/javascript",
            async: true,
            defer: true,
            src: item.getAttribute("src")
        };
        for (const [key, value] of Object.entries(props)) {
            g[key] = value;
        }
        b.appendChild(g);
    });
};
export function sendRequest (url, params) {

    params = params || {};
    // Return a new promise.
    return new Promise(function(resolve, reject) {
      // Do the usual XHR stuff
      var req = new XMLHttpRequest();
      req.open('GET', url);
      req.onload = function() {
        // This is called even on 404 etc
        // so check the status
        if (req.status == 200) {
          // Resolve the promise with the response text
          resolve(req.response);
        }
        else {
          // Otherwise reject with the status text
          // which will hopefully be a meaningful error
          reject(req);
        }
      };
  
      // Handle network errors
      req.onerror = function() {
        reject(Error("Network Error"));
      };
  
      // Make the request
      req.send();
    });
};

export function isInViewport(element) {
  if (!element) return false;
  const rect = element.getBoundingClientRect();
  return (
      rect.top >= 0 &&
      rect.left >= 0 &&
      rect.bottom < (window.innerHeight || document.documentElement.clientHeight) &&
      rect.right <= (window.innerWidth || document.documentElement.clientWidth)
  );
};

import {sendRequest, isInViewport, getUrlParameter} from "./Utility";
export default {
    mounted: function() {
        var self = this;
        Promise.all([
            sendRequest(self.settingsURL).catch(error => { return error }),
            sendRequest(self.meURL).catch(error => { return error }),
        ]).then(responses => {
            try {
                this.setSettings(JSON.parse(responses[0]));
            } catch(e) {
                self.setErrorMessage(`Error parsing data ${e}`);
            }
            try {
                self.userInfo = JSON.parse(responses[1]);
            } catch(e) {
                self.setErrorMessage(`Error parsing data ${e}`);
            }
            self.initApp();
            console.log("settings? ", self.settings);
            console.log("user? ", self.userInfo)
        }).catch(error => {
            self.setErrorMessage(`Error in promises ${error}`);
            self.initApp();
        });
    },
    /*
     * methods available to the application
     */
    methods: {
        isLoading: function() {
            return this.loading;
        },
        isInitialized: function() {
            return this.initialized;
        },
        initApp: function() {
            let self = this;
            this.setSettings(this.settings);
            this.setLRBaseURL(this.settings?this.settings["LR_ORIGIN"]:"");
            this.setUserID(this.userInfo?this.userInfo["id"]:0);
            this.initialized = true;
            Promise.all([
                 //TODO init user domains, call api based on user id
                sendRequest(`/api/demographics/${this.getUserID()}`).catch(error => { return error }),
            ]).then(responses => {
                try {
                    this.setLocale(JSON.parse(responses[0]));
                } catch(e) {
                    self.setErrorMessage(`Error parsing data ${e}`);
                }
                console.log("user locale? ", this.getLocale())
                //get welcome page
                //TODO filter content based on user's domains?
                //each domain link on the intro/welcome page should have a representative attribute or css class
                //that denote which domain it represents
                self.getDomainContent();
               // self.setInitView();
            }).catch(error => {
                self.setErrorMessage(`Error in promises ${error}`);
                self.setInitView();
            });
        },
        setInitView: function() {
            let self = this;
            Vue.nextTick(
                function() {
                    setTimeout(function() {
                        this.setCurrentView("domain");
                        this.loading = false;
                    }.bind(self), 350);
                }
            );
        },
        hasError: function() {
            return this.errorMessage !== "";
        },
        resetError: function() {
            this.setErrorMessage("");
        },
        setErrorMessage: function(message) {
            this.errorMessage += (this.errorMessage?"<br/>": "") + message;
        },
        getUserID: function() {
            return this.userId;
        },
        setUserID: function(id) {
            this.userId = id;
        },
        getLocale: function() {
            return this.locale.replace('_', '-');
        },
        setLocale: function(data) {
            let self = this;
            if (!data || !data.communication) {
                return false;
            }
            data.communication.forEach(function(item) {
                if (item.language &&
                    item.language.coding &&
                    item.language.coding.length) {
                    self.locale = item.language.coding[0].code;
                }
            });
            console.log("Locale ", this.locale);
        },
        getSettings: function() {
            return this.settings;
        },
        setSettings: function(data) {
            if (data) {
                this.settings = data;
            }
        },
        getUserInfo: function() {
            return this.userInfo;
        },
        setUserInfo: function(data) {
            if (data) {
                this.userInfo = data;
            }
        },
        getLRBaseURL: function() {
            return this.LifeRayBaseURL;
        },
        setLRBaseURL: function(data) {
            if (data) {
                this.LifeRayBaseURL = data;
            }
        },
        getCurrentView: function() {
            return this.currentView;
        },
        setCurrentView: function(viewId) {
            viewId = viewId || "domain";
            this.currentView = viewId;
        },
        isCurrentView: function(viewId) {
            //return !this.hasError() && !this.isLoading() && this.isMatchView(viewId);
            return !this.isLoading() && this.isMatchView(viewId);
        },
        isMatchView: function(viewId) {
            return this.currentView === viewId;
        },
        goToView: function(viewId) {
            Vue.nextTick(
                function() {
                    self.resetError();
                    self.setCurrentView(viewId);
                }
            );
        },
        setNav: function() {
            //let navElement = document.querySelector(".navigation .content");
            let navElement = document.querySelector(".navigation");
            //let mobileNavElement = document.querySelector(".mobile-navigation .content");
            let mobileNavElement = document.querySelector(".mobile-navigation");
            let mobileQuickLinkElement = document.querySelector(".mobile-quick-links");
            console.log("nav? ", navElement)
            if (!navElement) {
                if (mobileNavElement) {
                    mobileNavElement.classList.add("hide");
                }
                if (mobileQuickLinkElement) {
                    mobileQuickLinkElement.classList.add("hide");
                }
                return;
            }
            let anchorElements = document.querySelectorAll(".anchor-link");
            //console.log("anchor links? ", anchorElements)
            if (!anchorElements.length) {
                // let navParentElement = document.querySelector(".navigation");
                // let mobileNavElement = document.querySelector(".mobile-navigation");
                // let mobileQuickLinkElement = document.querySelector(".mobile-quick-links");
                if (navElement) navElement.classList.add("hide");
                if (mobileNavElement) mobileNavElement.classList.add("hide");
                if (mobileQuickLinkElement) mobileQuickLinkElement.classList.add("hide");
                return;
            }
            let navContentContainerElement = document.querySelector(".navigation .content");
            if (!navContentContainerElement) {
                let div = document.createElement("div");
                div.classList.add("content");
                navElement.prepend(div);
            }
            let contentHTML = "";
            anchorElements.forEach(el => {
                if (!el.getAttribute("id")) {
                    return true;
                }
                console.log("Next element? " , el.nextElementSibling.innerText)
                contentHTML += `<a href="#${el.getAttribute("id")}">${
                    el.nextElementSibling &&
                    el.nextElementSibling.innerText? 
                    el.nextElementSibling.innerText : el.getAttribute("id").replace(/_/g, ' ')}</a>`;
            });
            let contentElement = document.createElement("div");
            contentElement.innerHTML = contentHTML;
            let mobileContentElement = contentElement.cloneNode(true);
            navContentContainerElement.appendChild(contentElement);
            if (mobileNavElement) {
                let mobileNavContentContainerElement = document.querySelector(".mobile-navigation .content");
                if (!mobileNavContentContainerElement) {
                    let div = document.createElement("div");
                    div.classList.add("content");
                    mobileNavElement.prepend(div);
                }
                mobileNavContentContainerElement.appendChild(mobileContentElement);
                mobileNavElement.addEventListener("click",function(e) {
                    document.querySelector(".mobile-navigation").classList.remove("open");
                    document.querySelector("body").classList.remove("fixed");
                });
            }
            window.addEventListener("scroll", function(e) {
                window.requestAnimationFrame(function() {
                    let topPosition = 48;
                    if (isInViewport(document.querySelector("#tnthNavWrapper"))) {
                        topPosition = document.querySelector("#tnthNavWrapper").offsetHeight + 48;
                    }
                    document.querySelector(".navigation").style.top = topPosition+"px";
                });
            });
            let mobileLinkButton = document.querySelector(".mobile-quick-links button");
            if (mobileLinkButton) {
                mobileLinkButton.addEventListener("click",function(e) {
                    document.querySelector(".mobile-navigation").classList.add("open");
                    setTimeout(function() {
                        document.querySelector("body").classList.add("fixed");
                    }, 150);
                });
            }
            let self = this;
            // window.onload = function() {
            //     console.log("GET TO LOAD??")
            //     setTimeout(function() {
            //         self.setNavLeftPos()
            //     }, 50);
            // };
            //window.onload = self.setNavLeftPos;
            // setTimeout(function() {
            //     this.setNavLeftPos();
            // }.bind(this),150);
            window.addEventListener("resize", function() {
                let nav = document.querySelector(".mobile-navigation");
                if (nav) nav.classList.remove("open");
                document.querySelector("body").classList.remove("fixed");
                //self.setNavLeftPos();
            });
            let videoNavImage = document.querySelectorAll(".navigation-video-image");
            videoNavImage.forEach(el => {
                el.addEventListener("click", function(e) {
                    let videoElement = document.querySelector(".video");
                    if (videoElement) {
                        videoElement.scrollIntoView();
                    }
                });
            });
        },
        // setNavLeftPos: function() {
        //     if (isElementHidden(document.querySelector(".navigation"))) return;
        //  //   console.log("WTF?? ", document.querySelector("#domainSection").offsetWidth)
        //  let sectionElement = document.querySelector("#domainSection");
        //  let width = sectionElement.innerWidth || sectionElement.clientWidth || sectionElement.clientWidth;
        //  console.log("wtf? ", width)
        //     document.querySelector(".navigation").style.left = (width - document.querySelector(".navigation").offsetWidth - 16) + "px";
        // },
        setCollapsible: function() {
            let collapsibleElements = document.querySelectorAll(".collapsible");
            collapsibleElements.forEach(el => {
                el.addEventListener('click', event => {
                    //let collapsibleItems = document.querySelectorAll(".collapsible");
                    let parentEl = event.target.parentElement;
                    console.log("parent? ", parentEl)
                    let collapsibleItems = parentEl.querySelectorAll(".collapsible");
                    collapsibleItems.forEach(item => {
                        if (item === event.target) return true;
                        item.classList.remove("open");
                    });
                    if (event.target.classList.contains("open")) {
                        event.target.classList.remove("open");
                        return;
                    }
                    event.target.classList.add("open");
                });
            })
        },
        setTileLinkEvent: function() {
            let tileElements = document.querySelectorAll(".tiles-container .tile");
            tileElements.forEach(el => {
                let anchorLink = el.querySelector("a");
                if (anchorLink && anchorLink.getAttribute("href")) {
                    el.addEventListener("click", function(e) {
                        e.stopPropagation();
                        window.open(anchorLink.getAttribute("href"), "_blank");
                        return false;
                    });
                }
            });
            // $(".tiles-container .tile").each(function() {
            //     let anchorLink = $(this).find("a");
            //     if (anchorLink.length && $(anchorLink).attr("href")) {
            //         $(this).on("click", function(e) {
            //             e.stopPropagation();
            //             window.open($(anchorLink).attr("href"), "_blank");
            //             return false;
            //         });
            //     }
            // });
        },
        setVideo: function() {
            let videoElement = document.querySelector(".video");
            if (!videoElement) {
                return;
            }
            let iframeElement = document.createElement("iframe");
            let iframeSrc = videoElement.getAttribute("data-iframe-src");
            let videoNavElements = document.querySelectorAll(".navigation-video-image");
            if (!iframeSrc) {
                let videoSection = document.querySelector(".video-section");
                if (videoSection) {
                    videoSection.classList.add("hide");
                }
                videoNavElements.forEach(item => {
                    item.classList.add("hide");
                });
                return;
            }
            iframeElement.setAttribute("allowfullscreen", true);
            iframeElement.setAttribute("src", videoElement.getAttribute("data-iframe-src"));
            videoElement.appendChild(iframeElement);
            videoElement.classList.add("active");
            videoNavElements.forEach(el => {
                el.addEventListener("click", event => {
                    let ve = document.querySelector(".video iframe");
                    if (ve) {
                        let veSrc = ve.getAttribute("src");
                        if (veSrc.indexOf("?") !== -1) {
                            veSrc = veSrc.substring(0, veSrc.indexOf("?"));
                        }
                        ve.setAttribute("src", veSrc + "?autoPlay=true");
                    }
                })
            });
        },
        getSelectedDomain: function() {
            //return this.activeDomain;
            //return "substudy";
            //return "hot_flashes"
            return getUrlParameter("topic") || "mood_changes";
         },
         getSearchURL: function() {
             //TODO use current domain name as tag
             //pass in locale info
             return `/api/asset/tag/${this.getSelectedDomain()}?locale_code=${this.getLocale()}`;
             //CORS issue with querying LR directly, TODO: uncomment this when resolves
            //  return  `${this.getLRBaseURL()}/c/portal/truenth/asset/query?content=true&anyTags=${this.getSelectedDomain()}&languageId=${this.getLocale()}`;
         },
        getDomainContent: function() {
            if (this.domainContent) {
                //already populated
                this.setInitView();
                return this.domainContent;
            }
            let self = this;
            // $.ajax({
            //     url : this.getSearchURL(),
            //     crossDomain : true,
            //     cache : false,   //if needed..
            //     type : 'GET',    //Default..
            //     retryCount : 0,
            //     retryLimit : 3,
            //     xhrFields : {
            //         withCredentials : true //if needed..
            //     }}).done(function(data) {
            //         console.log("data? ", data)
            //     }).fail(function(e) {
            //         console.log("failed ")
            //     });
            sendRequest(this.getSearchURL()).then(response => {
                //LR URL returns this
                //console.log("response? ", JSON.parse(response));
                // let content = JSON.parse(response);
                // this.setDomainContent(content["results"][0]["content"]);
                //console.log("response? ", response);
                if (response) {
                    this.setDomainContent(response);
                    Vue.nextTick()
                    .then(function () {
                        // DOM updated
                        self.setNav();
                        self.setCollapsible();
                        self.setVideo();
                        self.setTileLinkEvent();
                        setTimeout(function() {
                            this.setInitView();
                            this.setCurrentView("domain");
                        }.bind(self), 150);
                    })
                    // setTimeout(function() {
                    //     this.setNav();
                    //     this.setCollapsible();
                    //     this.setVideo();
                    //     this.setTileLinkEvent();

                    //     setTimeout(function() {
                    //         this.setInitView();
                    //         this.setCurrentView("domain");
                    //     }.bind(this), 50);
                    // }.bind(this), 200);
                    
                } else {
                    this.setErrorMessage(`Error occurred retrieving content: no content returned.`);
                    this.setInitView();
                }
            }).catch(e => {
                console.log("failed? ", e)
                this.getContentAttempt++;
                if (this.getContentAttempt <= 2) {
                    this.getDomainContent();
                    return;
                } else {
                    this.getContentAttempt = 0;
                }
                this.setErrorMessage(`Error occurred retrieving content: ${e.responseText}`);
                this.setInitView();
            });
        },
        setDomainContent: function(data) {
            this.domainContent = data;
        },
        goHome: function() {
            this.goToView("domain");
        }
    }
};

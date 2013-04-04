/*jslint vars: false, nomen: true, browser: true */
/*global $, Home */

if (window.Home === undefined) {
    Home = {};
}

Home.init = function () {
    $(".jumbotron a").click(function (e) {
        $(e.target).addClass("disabled");
        $("#sign-up-block").fadeIn();
        $(e.target).unbind("click");
    });
};

$(document).ready(Home.init());

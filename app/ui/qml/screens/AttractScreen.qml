import QtQuick
import QtQuick.Layouts
import "../components"
import SellMate 1.0

Item {
    id: root

    // Bleed past AppShell page margins so GIFs are edge-to-edge.
    anchors.fill: parent
    anchors.leftMargin: -Theme.pageMargin
    anchors.rightMargin: -Theme.pageMargin
    anchors.topMargin: -(Theme.pageMargin + 4)
    anchors.bottomMargin: -Theme.pageMargin

    readonly property bool active: App.screen === "attract"
    readonly property var gifUrls: Theme.attractGifUrls
    readonly property bool hasGifs: gifUrls && gifUrls.length > 0
    property int gifIndex: 0

    onActiveChanged: {
        if (active) {
            gifIndex = 0
            carouselTimer.restart()
        } else {
            carouselTimer.stop()
        }
    }

    // --- Full-bleed GIF idle layer ---
    Rectangle {
        anchors.fill: parent
        color: "#111111"
        visible: root.hasGifs
    }

    Repeater {
        model: root.hasGifs ? root.gifUrls.length : 0
        delegate: AnimatedImage {
            required property int index
            anchors.fill: parent
            source: root.gifUrls[index]
            fillMode: Image.PreserveAspectCrop
            opacity: index === root.gifIndex ? 1 : 0
            playing: root.active && index === root.gifIndex
            cache: true
            asynchronous: true
            z: 0

            Behavior on opacity {
                NumberAnimation {
                    duration: Math.max(200, Theme.animationMs)
                    easing.type: Easing.InOutQuad
                }
            }
        }
    }

    // Soft bottom scrim so the pink CTA stays readable over any GIF.
    Rectangle {
        visible: root.hasGifs
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: parent.height * 0.42
        z: 1
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#00000000" }
            GradientStop { position: 0.45; color: "#66000000" }
            GradientStop { position: 1.0; color: "#B3000000" }
        }
    }

    Timer {
        id: carouselTimer
        interval: Math.max(2000, Theme.attractGifIntervalMs)
        repeat: true
        running: root.active && root.hasGifs && root.gifUrls.length > 1
        onTriggered: root.gifIndex = (root.gifIndex + 1) % root.gifUrls.length
    }

    // Tap anywhere on the media to start (button sits above this).
    MouseArea {
        anchors.fill: parent
        z: 2
        enabled: root.hasGifs
        onClicked: App.enterBrowse()
    }

    // Fallback brand stack when GIFs are unavailable.
    ColumnLayout {
        visible: !root.hasGifs
        anchors.fill: parent
        anchors.leftMargin: Theme.pageMargin
        anchors.rightMargin: Theme.pageMargin
        anchors.topMargin: Theme.pageMargin + 4
        anchors.bottomMargin: Theme.pageMargin
        spacing: Theme.sectionGap
        z: 5

        Item { Layout.fillHeight: true; Layout.preferredHeight: 3 }

        Image {
            visible: Theme.logoUrl.length > 0
            source: Theme.logoUrl
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredHeight: 88
            Layout.preferredWidth: parent.width * 0.55
            fillMode: Image.PreserveAspectFit
            asynchronous: true
        }

        Text {
            text: Theme.businessName
            color: Theme.primary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.titleFontPx + 8
            font.bold: true
            horizontalAlignment: Text.AlignHCenter
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
        }

        Text {
            text: Theme.attractHeadline
            color: Theme.textMuted
            font.family: Theme.fontFamily
            font.pixelSize: Theme.subtitleFontPx
            horizontalAlignment: Text.AlignHCenter
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
        }

        PromoBanner {
            Layout.fillWidth: true
        }

        Item { Layout.fillHeight: true; Layout.preferredHeight: 2 }

        PrimaryButton {
            text: "Start shopping"
            pink: true
            Layout.fillWidth: true
            onClicked: App.enterBrowse()
        }

        Item { Layout.fillHeight: true; Layout.preferredHeight: 1 }
    }

    // Pink CTA layered above the GIF plane.
    PrimaryButton {
        visible: root.hasGifs
        text: "Start shopping"
        pink: true
        z: 10
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.leftMargin: Theme.pageMargin
        anchors.rightMargin: Theme.pageMargin
        anchors.bottomMargin: Theme.pageMargin + 12
        onClicked: App.enterBrowse()
    }

    MouseArea {
        anchors.fill: parent
        z: -1
        enabled: !root.hasGifs
        onClicked: App.enterBrowse()
    }
}
